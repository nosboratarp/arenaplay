from upload_drive import upload_para_drive

file_id = upload_para_drive("teste.mp4")

print("Upload concluído")
print("Link:", f"https://drive.google.com/file/d/{file_id}/preview")
