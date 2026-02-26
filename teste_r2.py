import boto3

R2_ENDPOINT = "https://98b8d67b244a59186a4e844503edcec4.r2.cloudflarestorage.com"
R2_ACCESS_KEY = "c2e0a8702b0c63b8c6158c7601f42724"
R2_SECRET_KEY = "4451e6af9dd6734e851f40496d16357d4dc009d467da63634d6667252fc3047a"

BUCKET = "arenavision-videos"

s3 = boto3.client(
    service_name="s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    region_name="auto"
)

# Upload de teste
arquivo_local = "teste.mp4"
nome_no_bucket = "teste.mp4"

s3.upload_file(arquivo_local, BUCKET, nome_no_bucket)

print("✅ Upload realizado com sucesso!")