import os
import socket

try:
    import pyroscope

    pyroscope.configure(
        application_name="jupyter.singleuser",
        server_address=os.getenv("PYROSCOPE_SERVER_ADDRESS", "http://pyroscope.monitoring.svc.cluster.local:4040"),
        sample_rate=100,
        oncpu=True,
        gil_only=True,
        tags={
            "user": os.getenv("JUPYTERHUB_USER", "unknown"),
            "pod": socket.gethostname(),
            "namespace": os.getenv("NAMESPACE", "default"),
        },
    )
except Exception as e:
    print(f"[pyroscope] skipped: {e}")