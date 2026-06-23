Triton Deployment at Coffea-Casa facility
=================

This environment provides access to a Triton inference server deployment with 2 GPUs. Credentials for the Triton model repository are mounted in the session and are available through environment variables.

Available Deployment
--------------------

- Triton server accessible at ``triton-grpc.cmsaf-prod.flatiron.hollandhpc.org``
- 2 GPUs available for inference
- Model repository backed by S3-compatible storage
- Credentials mounted in the session via ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``TRITON_BUCKET_HOST``, and ``TRITON_BUCKET_NAME``

Uploading Models
----------------

Use the following example to upload a model directory to the mounted Triton model repository bucket:

.. code-block:: python

    import boto3
    import os
    from pathlib import Path

    s3 = boto3.client(
        "s3",
        endpoint_url=f"http://{os.environ['TRITON_BUCKET_HOST']}",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )

    def upload_directory(local_path: str, bucket: str, s3_prefix: str = ""):
        local = Path(local_path)

        for file_path in local.rglob("*"):
            if file_path.is_file():
                s3_key = f"{s3_prefix}/{file_path.relative_to(local)}".lstrip("/")
                print(f"Uploading {file_path} -> s3://{bucket}/{s3_key}")
                s3.upload_file(str(file_path), bucket, s3_key)

    upload_directory(
        local_path="reconstruction_bdt_xgb",
        bucket=os.environ["TRITON_BUCKET_NAME"],
        s3_prefix="reconstruction_bdt_xgb",
    )

Accessing Triton from Coffea-Casa
---------------------------------

Connect to Triton from coffea-casa using the GRPC endpoint:

- ``triton-grpc.cmsaf-prod.flatiron.hollandhpc.org``

If a port is required, use the standard Triton gRPC port, for example:

- ``triton-grpc.cmsaf-prod.flatiron.hollandhpc.org:8001``
