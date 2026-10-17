"""Poll /health during a Beanstalk deployment and summarize which versions
and instances answered. Stop it with Ctrl+C once the deployment finishes.

Usage: python scripts/watch_deploy.py <base_url> [--interval 1] [--log file]
"""
import argparse
import json
import time
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import urlopen


def poll(url, timeout):
    """Return (status code or None, version, instance) for one request."""
    try:
        with urlopen(url, timeout=timeout) as response:
            status, body = response.status, json.load(response)
    except HTTPError as error:
        status = error.code
        try:
            body = json.load(error)
        except ValueError:
            body = {}
    except (OSError, ValueError) as error:
        return None, "-", type(error).__name__
    if not isinstance(body, dict):
        body = {}
    return status, body.get("version", "-"), body.get("instance", "-")


def summarize(total, errors, versions, instances, started):
    elapsed = time.monotonic() - started
    lines = [
        "",
        "--- Resumen " + "-" * 44,
        "Duracion del monitoreo: {:.0f} s   Peticiones: {}   Errores: {}".format(elapsed, total, errors),
        "",
        "Versiones (respuestas, primera vez, ultima vez):",
    ]
    for version, seen in versions.items():
        lines.append("  {:<12} {:>5}   {}   {}".format(version, seen["count"], seen["first"], seen["last"]))
    if len(versions) > 1:
        (old, old_seen), (new, new_seen) = list(versions.items())[0], list(versions.items())[-1]
        lines.append("Primera respuesta de {}: {}   Ultima respuesta de {}: {}".format(
            new, new_seen["first"], old, old_seen["last"]))
    lines += ["", "Instancias (respuestas, primera vez, ultima vez, versiones servidas):"]
    for instance, seen in instances.items():
        lines.append("  {:<22} {:>5}   {}   {}   {}".format(
            instance, seen["count"], seen["first"], seen["last"], ", ".join(seen["versions"])))
    lines.append("Total de instancias vistas: {}".format(len(instances)))
    return lines


def track(seen, key, now):
    """Record a sighting; return True the first time a key appears."""
    if key not in seen:
        seen[key] = {"count": 0, "first": now, "last": now, "versions": []}
    seen[key]["count"] += 1
    seen[key]["last"] = now
    return seen[key]["count"] == 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base_url", help="URL del ambiente, por ejemplo http://mi-env.us-east-1.elasticbeanstalk.com")
    parser.add_argument("--interval", type=float, default=1.0, help="segundos entre peticiones (por defecto 1)")
    parser.add_argument("--timeout", type=float, default=3.0, help="segundos de espera por peticion (por defecto 3)")
    parser.add_argument("--log", help="archivo donde guardar tambien cada linea")
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/health"
    log = open(args.log, "a", encoding="utf-8") if args.log else None
    total = errors = 0
    versions, instances = {}, {}
    started = time.monotonic()
    print("Monitoreando {} cada {} s. Ctrl+C para terminar.\n".format(url, args.interval))
    try:
        while True:
            status, version, instance = poll(url, args.timeout)
            now = datetime.now().strftime("%H:%M:%S")
            total += 1
            notes = []
            if status != 200:
                errors += 1
            else:
                if track(versions, version, now) and len(versions) > 1:
                    notes.append("nueva version")
                if track(instances, instance, now):
                    notes.append("primera vez de esta instancia")
                if version not in instances[instance]["versions"]:
                    instances[instance]["versions"].append(version)
            line = "{}  {:>4}  {:<10}  {}{}".format(
                now, status or "ERR", version, instance, "   <- " + ", ".join(notes) if notes else "")
            print(line, flush=True)
            if log:
                log.write(line + "\n")
                log.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        for line in summarize(total, errors, versions, instances, started):
            print(line)
            if log:
                log.write(line + "\n")
    finally:
        if log:
            log.close()


if __name__ == "__main__":
    main()
