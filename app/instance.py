from urllib.request import Request, urlopen

METADATA_URL = "http://169.254.169.254/latest"
_instance_id = None


def ec2_instance_id():
    """Return the EC2 instance ID using IMDSv2, or "local" outside EC2."""
    global _instance_id
    if _instance_id is None:
        try:
            token_request = Request(
                METADATA_URL + "/api/token",
                method="PUT",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
            )
            token = urlopen(token_request, timeout=0.5).read().decode()
            id_request = Request(
                METADATA_URL + "/meta-data/instance-id",
                headers={"X-aws-ec2-metadata-token": token},
            )
            _instance_id = urlopen(id_request, timeout=0.5).read().decode()
        except OSError:
            _instance_id = "local"
    return _instance_id
