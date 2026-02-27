import boto3
import os
from datetime import datetime

R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")

BUCKET = "arenavision-videos"

s3 = boto3.client(
    service_name="s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    region_name="auto"
)

def upload_para_r2(caminho_arquivo):

    hoje = datetime.now().strftime("%Y-%m-%d")
    nome_arquivo = os.path.basename(caminho_arquivo)
    key = f"{hoje}/{nome_arquivo}"

    s3.upload_file(
        caminho_arquivo,
        BUCKET,
        key,
        ExtraArgs={
            "ContentType": "video/mp4",
            "CacheControl": "public, max-age=31536000"
        }
    )

    return key