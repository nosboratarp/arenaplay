
import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
import cv2
import time
from collections import deque
import threading
import winsound
import pygame
import time
from upload_r2 import upload_para_r2


pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("Ã¢ï¿½Å’ Nenhum encoder detectado!")
    exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()
print("Ã¢Å“â€¦ Encoder pronto:", joystick.get_name())


#from upload_exa_cloud import upload_video
#from upload_google_drive import upload_video
#from upload_google_drive_oauth import upload_video
# ===== CONFIGURAÃƒâ€¡Ãƒâ€¢ES =====
FPS = 15
PRE_SECONDS = 10
POST_SECONDS = 3
BUFFER_SIZE = FPS * PRE_SECONDS
VIDEO_NAME = "lance_teste.mp4"

# ===== PASTA DA SESSÃƒÆ’O =====
SESSION_DATE = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join(os.getcwd(), "lances", SESSION_DATE)
os.makedirs(BASE_DIR, exist_ok=True)


# ===== CÃƒâ€šMERA =====
# ===== CÃƒâ€šMERA (IM5 SC via RTSP) =====
RTSP_URL = "rtsp://admin:Networks124@192.168.3.135:1857/cam/realmonitor?channel=1&subtype=0"

cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)

time.sleep(2)  # estabiliza o stream

ret, frame = cap.read()


if not ret:
    print("Erro ao conectar na cÃƒÂ¢mera RTSP")
    exit()

height, width, _ = frame.shape



buffer = deque(maxlen=BUFFER_SIZE)
cooldown = False

print("Sistema iniciado")
print("Pressione o Botao para salvar o lance")
print("Pressione 'Q' para sair")

# ===== FUNÃƒâ€¡ÃƒÆ’O DE SALVAMENTO =====
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

    # ===============================
    # ESCREVER FRAMES COM MARCA
    # ===============================
    for frame in frames:

        overlay = frame.copy()

        texto = "ArenaPlay"
        font = cv2.FONT_HERSHEY_SIMPLEX
        escala = 3.5
        espessura = 8

        (text_width, text_height), _ = cv2.getTextSize(texto, font, escala, espessura)

        pos_x = (width - text_width) // 2
        pos_y = (height + text_height) // 2

        cv2.putText(
            overlay,
            texto,
            (pos_x, pos_y),
            font,
            escala,
            (0, 255, 0),
            espessura
        )

        alpha = 0.25
        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

        out.write(frame)

    out.release()

    print(f"Lance salvo localmente: {video_path}")

    # ===============================
    # UPLOAD PARA O DRIVE
    # ===============================
    try:
        print("Enviando para o R2...")
        file_id = upload_para_r2(video_path)
        print("[R2] Upload concluído com sucesso!")
    except Exception as e:
        print("Erro ao enviar para o Drive:", e)
        cooldown = False
        return

    # ===============================
    # REGISTRAR NO BANCO
    # ===============================
    try:
        from app import app, db, Lance

        data = SESSION_DATE
        hora = timestamp.replace("-", ":")

        with app.app_context():
            novo_lance = Lance(
                quadra="oratorio2",
                data=data,
                hora=hora,
                drive_id=file_id
            )
            db.session.add(novo_lance)
            db.session.commit()

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
            print("Ã°Å¸Å¸Â¡ Sistema ativo Ã¢â‚¬â€� aguardando novo stream da cÃƒÂ¢mera para prÃƒÂ³ximos lances...")
            aguardando_stream = True

        time.sleep(0.2)

        if falhas_consecutivas >= MAX_FALHAS:
            print("Ã°Å¸â€�â€ž Reconectando cÃƒÂ¢mera RTSP...")
            cap.release()
            time.sleep(2)
            cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
            falhas_consecutivas = 0

        continue

    # ===== STREAM VOLTOU =====
    if aguardando_stream:
        print("Ã°Å¸Å¸Â¢ Stream restabelecido Ã¢â‚¬â€� sistema pronto para novo lance")
        aguardando_stream = False

    falhas_consecutivas = 0

    # ===== BUFFER =====
    buffer.append(frame)

    # ===== EXIBIÃƒâ€¡ÃƒÆ’O =====
    cv2.imshow("Meu Lance - Teste", frame)

    # ===== TECLADO (apenas para sair) =====
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q') or key == ord('Q'):
        print("Encerrando pelo usuÃƒÂ¡rio")
        break

    # ===== BOTAO FISICO (encoder USB) =====
    pygame.event.pump()

    if joystick.get_button(0):  # botÃƒÂ£o nÃƒÂºmero 0
        if not cooldown:
            print("Botao Fisico detectado")
            threading.Thread(target=salvar_lance).start()
            time.sleep(1)  # evita vÃƒÂ¡rios disparos seguidos




cap.release()
cv2.destroyAllWindows()
