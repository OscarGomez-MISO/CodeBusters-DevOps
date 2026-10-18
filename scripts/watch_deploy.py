"""Poll /health during a Beanstalk deployment and summarize which versions
answered. Stop it with Ctrl+C once the deployment finishes.

Usage: python scripts/watch_deploy.py <base_url> [--interval 1] [--log file]
"""
import argparse
import json
import time
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import urlopen


def poll(url, timeout):
    """Return (status code or None, version) for one request."""
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
        return None, type(error).__name__
    if not isinstance(body, dict):
        body = {}
    return status, body.get("version", "-")


def summarize(total, errors, versions, started):
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
    return lines


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
    versions = {}
    started = time.monotonic()
    print("Monitoreando {} cada {} s. Ctrl+C para terminar.\n".format(url, args.interval))
    try:
        while True:
            status, version = poll(url, args.timeout)
            now = datetime.now().strftime("%H:%M:%S")
            total += 1
            note = ""
            if status != 200:
                errors += 1
            else:
                if version not in versions:
                    versions[version] = {"count": 0, "first": now}
                    if len(versions) > 1:
                        note = "   <- nueva version"
                versions[version]["count"] += 1
                versions[version]["last"] = now
            line = "{}  {:>4}  {}{}".format(now, status or "ERR", version, note)
            print(line, flush=True)
            if log:
                log.write(line + "\n")
                log.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        for line in summarize(total, errors, versions, started):
            print(line)
            if log:
                log.write(line + "\n")
    finally:
        if log:
            log.close()


if __name__ == "__main__":
    main()
