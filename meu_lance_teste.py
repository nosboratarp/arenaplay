import os
from datetime import datetime
import cv2
import time
from collections import deque
import threading
import winsound
import pygame
import time
from upload_drive import upload_para_drive


pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("❌ Nenhum encoder detectado!")
    exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()
print("✅ Encoder pronto:", joystick.get_name())


#from upload_exa_cloud import upload_video
#from upload_google_drive import upload_video
#from upload_google_drive_oauth import upload_video
# ===== CONFIGURAÇÕES =====
FPS = 15
PRE_SECONDS = 30
POST_SECONDS = 5
BUFFER_SIZE = FPS * PRE_SECONDS
VIDEO_NAME = "lance_teste.mp4"

# ===== PASTA DA SESSÃO =====
SESSION_DATE = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join(os.getcwd(), "lances", SESSION_DATE)
os.makedirs(BASE_DIR, exist_ok=True)


# ===== CÂMERA =====
# ===== CÂMERA (IM5 SC via RTSP) =====
RTSP_URL = "rtsp://admin:Networks124@192.168.3.135:1857/cam/realmonitor?channel=1&subtype=0"

cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)

time.sleep(2)  # estabiliza o stream

ret, frame = cap.read()


if not ret:
    print("Erro ao conectar na câmera RTSP")
    exit()

height, width, _ = frame.shape



buffer = deque(maxlen=BUFFER_SIZE)
cooldown = False

print("Sistema iniciado")
print("Pressione o Botao para salvar o lance")
print("Pressione 'Q' para sair")

# ===== FUNÇÃO DE SALVAMENTO =====
def salvar_lance():
    global cooldown
    cooldown = True

    print("Salvando lance...")

    timestamp = datetime.now().strftime("%H-%M-%S")
    video_name = f"lance_{timestamp}.mp4"
    video_path = os.path.join(BASE_DIR, video_name)

    frames = list(buffer)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, FPS, (width, height))

    for frame in frames:
        out.write(frame)

    out.release()

    print(f"Lance salvo localmente: {video_path}")

    # ===============================
    # UPLOAD PARA O DRIVE
    # ===============================
    try:
        print("Enviando para o Drive...")

        file_id = upload_para_drive(video_path)

        drive_link = f"https://drive.google.com/file/d/{file_id}/preview"

        print("[DRIVE] Upload concluído com sucesso!")
        print("[DRIVE] Link:", drive_link)

    except Exception as e:
        print("Erro ao enviar para o Drive:", e)
        file_id = None
        drive_link = None

    # ===============================
    # REGISTRAR NO BANCO
    # ===============================
    try:
        from database import salvar_lance as registrar_lance

        data = SESSION_DATE
        hora = timestamp.replace("-", ":")

        registrar_lance(
            quadra="oratorio1",
            data=data,
            hora=hora,
            drive_id=file_id
        )

        print("Lance registrado no banco.")

    except Exception as e:
        print("Erro ao registrar no banco:", e)

    # ===============================
    # SOM DE CONFIRMAÇÃO
    # ===============================
    try:
        winsound.Beep(1000, 120)
        winsound.Beep(1200, 120)
    except:
        pass

    cooldown = False

# ===== CONTROLE DE ESTADO =====
aguardando_stream = False
MAX_FALHAS = 15
falhas_consecutivas = 0

# ===== LOOP PRINCIPAL =====
while True:
    ret, frame = cap.read()

    # ===== TRATAMENTO DE FALHA RTSP =====
    if not ret:
        falhas_consecutivas += 1

        if not aguardando_stream:
            print("🟡 Sistema ativo — aguardando novo stream da câmera para próximos lances...")
            aguardando_stream = True

        time.sleep(0.2)

        if falhas_consecutivas >= MAX_FALHAS:
            print("🔄 Reconectando câmera RTSP...")
            cap.release()
            time.sleep(2)
            cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
            falhas_consecutivas = 0

        continue

    # ===== STREAM VOLTOU =====
    if aguardando_stream:
        print("🟢 Stream restabelecido — sistema pronto para novo lance")
        aguardando_stream = False

    falhas_consecutivas = 0

    # ===== BUFFER =====
    buffer.append(frame)

    # ===== EXIBIÇÃO =====
    cv2.imshow("Meu Lance - Teste", frame)

    # ===== TECLADO (apenas para sair) =====
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q') or key == ord('Q'):
        print("Encerrando pelo usuário")
        break

    # ===== BOTÃO FÍSICO (encoder USB) =====
    pygame.event.pump()

    if joystick.get_button(0):  # botão número 0
        if not cooldown:
            print("Botão físico detectado")
            threading.Thread(target=salvar_lance).start()
            time.sleep(1)  # evita vários disparos seguidos




cap.release()
cv2.destroyAllWindows()
