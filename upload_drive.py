import os
import pickle
from datetime import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/drive']

PASTA_ORATORIO_ID = "17ZR7xXiOVbyowSudpBVe5gbF2Xgpwgtt"  # Pasta principal Oratorio1


def autenticar():
    creds = None

    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'oauth_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds


def criar_ou_buscar_pasta(service, nome_pasta, parent_id):
    query = f"name='{nome_pasta}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"

    results = service.files().list(
        q=query,
        fields="files(id, name)"
    ).execute()

    files = results.get('files', [])

    if files:
        return files[0]['id']

    file_metadata = {
        'name': nome_pasta,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }

    folder = service.files().create(
        body=file_metadata,
        fields='id'
    ).execute()

    return folder.get('id')


def upload_para_drive(caminho_arquivo):
    creds = autenticar()
    service = build('drive', 'v3', credentials=creds)

    hoje = datetime.now().strftime("%Y-%m-%d")

    # Criar ou buscar pasta da data
    pasta_data_id = criar_ou_buscar_pasta(service, hoje, PASTA_ORATORIO_ID)

    file_metadata = {
        'name': os.path.basename(caminho_arquivo),
        'parents': [pasta_data_id]
    }

    media = MediaFileUpload(caminho_arquivo, resumable=True)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    file_id = file.get('id')

    # Tornar público
    service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    return file_id
