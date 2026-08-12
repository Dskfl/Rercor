import cv2
import numpy as np
import os
from pathlib import Path
from tkinter import Tk, filedialog, messagebox
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from rembg import remove

# ============================================================
# CONFIGURACIÓN
# ============================================================
CARD_WIDTH_MM = 85.60
CARD_HEIGHT_MM = 54.00
MARGIN_MM = 10
SEPARATION_MM = 8
OUTPUT_WIDTH = 1200

def mm_to_points(mm):
    return mm * 72 / 25.4

# ============================================================
# ORDENAR ESQUINAS
# ============================================================
def ordenar_puntos(puntos):
    puntos = np.array(puntos, dtype=np.float32)
    suma = puntos.sum(axis=1)
    diferencia = np.diff(puntos, axis=1).reshape(-1)
    
    arriba_izquierda = puntos[np.argmin(suma)]
    abajo_derecha = puntos[np.argmax(suma)]
    arriba_derecha = puntos[np.argmin(diferencia)]
    abajo_izquierda = puntos[np.argmax(diferencia)]
    
    return np.array([
        arriba_izquierda, arriba_derecha, abajo_derecha, abajo_izquierda
    ], dtype=np.float32)

# ============================================================
# DETECTAR CON INTELIGENCIA ARTIFICIAL (V3)
# ============================================================
def detectar_con_ia(imagen):
    alto, ancho = imagen.shape[:2]
    max_dim = 800
    escala = 1
    
    if max(alto, ancho) > max_dim:
        escala = max_dim / max(alto, ancho)
        img_procesar = cv2.resize(imagen, (int(ancho * escala), int(alto * escala)))
    else:
        img_procesar = imagen.copy()

    img_rgb = cv2.cvtColor(img_procesar, cv2.COLOR_BGR2RGB)
    img_sin_fondo = remove(img_rgb)
    mascara = img_sin_fondo[:, :, 3] 
    
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return None
        
    contorno_max = max(contornos, key=cv2.contourArea)
    rectangulo = cv2.minAreaRect(contorno_max)
    puntos = cv2.boxPoints(rectangulo)
    
    esquinas = puntos / escala
    return ordenar_puntos(esquinas)

# ============================================================
# RECORTE MANUAL (ASISTENTE)
# ============================================================
def seleccion_manual(imagen, titulo="Selecciona y presiona ENTER"):
    alto, ancho = imagen.shape[:2]
    max_dim = 800
    escala = 1

    if max(alto, ancho) > max_dim:
        escala = max_dim / max(alto, ancho)
        img_mostrar = cv2.resize(imagen, (int(ancho * escala), int(alto * escala)))
    else:
        img_mostrar = imagen.copy()

    roi = cv2.selectROI(titulo, img_mostrar, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(titulo)

    x, y, w, h = roi
    if w > 0 and h > 0:
        x, y = int(x / escala), int(y / escala)
        w, h = int(w / escala), int(h / escala)
        return np.array([
            [x, y], [x + w, y], [x + w, y + h], [x, y + h]
        ], dtype=np.float32)
    else:
        return np.array([
            [0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]
        ], dtype=np.float32)

# ============================================================
# CORREGIR PERSPECTIVA Y RECORTAR
# ============================================================
def recortar_cedula(imagen, esquinas):
    ancho_salida = OUTPUT_WIDTH
    alto_salida = int(ancho_salida / (CARD_WIDTH_MM / CARD_HEIGHT_MM))

    destino = np.array([
        [0, 0], [ancho_salida - 1, 0], 
        [ancho_salida - 1, alto_salida - 1], [0, alto_salida - 1]
    ], dtype=np.float32)

    matriz = cv2.getPerspectiveTransform(esquinas, destino)
    return cv2.warpPerspective(imagen, matriz, (ancho_salida, alto_salida))

# ============================================================
# PROCESAR UNA FOTO
# ============================================================
def procesar_foto(ruta, salida, tipo_cara):
    imagen = cv2.imread(str(ruta))
    if imagen is None:
        raise Exception(f"No se pudo abrir:\n{ruta}")
    
    print(f"Analizando {tipo_cara} con IA...")
    esquinas = detectar_con_ia(imagen)
    
    if esquinas is None:
        messagebox.showwarning(
            "Modo Manual",
            f"La IA no pudo detectar el {tipo_cara}.\n\n"
            "Dibuja un rectángulo alrededor de la cédula y presiona ENTER."
        )
        esquinas = seleccion_manual(imagen, f"Recortar {tipo_cara}")
    
    resultado = recortar_cedula(imagen, esquinas)
    
    if not cv2.imwrite(str(salida), resultado):
        raise Exception(f"No se pudo guardar:\n{salida}")
    return salida

# ============================================================
# CREAR PDF
# ============================================================
def crear_pdf(frente, reverso, archivo_pdf):
    ancho_pagina, alto_pagina = letter
    ancho_tarjeta = mm_to_points(CARD_WIDTH_MM)
    alto_tarjeta = mm_to_points(CARD_HEIGHT_MM)
    margen = mm_to_points(MARGIN_MM)
    separacion = mm_to_points(SEPARATION_MM)

    pdf = canvas.Canvas(str(archivo_pdf), pagesize=letter)
    x = (ancho_pagina - ancho_tarjeta) / 2
    y_frente = (alto_pagina - margen - alto_tarjeta)
    
    pdf.drawImage(str(frente), x, y_frente, width=ancho_tarjeta, height=alto_tarjeta, preserveAspectRatio=False)
    
    y_reverso = (y_frente - separacion - alto_tarjeta)
    pdf.drawImage(str(reverso), x, y_reverso, width=ancho_tarjeta, height=alto_tarjeta, preserveAspectRatio=False)
    
    pdf.setFont("Helvetica", 7)
    pdf.drawCentredString(ancho_pagina / 2, margen / 2, "Frente y reverso de documento")
    pdf.save()

# ============================================================
# INTERFAZ
# ============================================================
def seleccionar_archivo(titulo):
    return filedialog.askopenfilename(
        title=titulo,
        filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Todos los archivos", "*.*")]
    )

def ejecutar():
    frente = seleccionar_archivo("Selecciona la FOTO DEL FRENTE")
    if not frente: return
    
    reverso = seleccionar_archivo("Selecciona la FOTO DEL REVERSO")
    if not reverso: return

    try:
        escritorio = Path.home() / "OneDrive" / "Desktop"
        carpeta = escritorio / "salida_cedulas"
        carpeta.mkdir(parents=True, exist_ok=True)

        frente_salida = carpeta / "frente_recortado.png"
        reverso_salida = carpeta / "reverso_recortado.png"
        pdf_salida = carpeta / "cedula_lista_para_imprimir.pdf"

        procesar_foto(frente, frente_salida, "FRENTE")
        procesar_foto(reverso, reverso_salida, "REVERSO")
        
        crear_pdf(frente_salida, reverso_salida, pdf_salida)

        # NUEVO: Preguntar si desea mandar a imprimir directamente
        imprimir_directo = messagebox.askyesno(
            "Impresión Directa", 
            "¡PDF creado con éxito!\n\n¿Deseas enviarlo directamente a la impresora predeterminada?"
        )

        if imprimir_directo:
            # Envía el archivo a imprimir usando el sistema de Windows
            os.startfile(str(pdf_salida), "print")
            messagebox.showinfo("Impresión", "Documento enviado a la impresora correctamente.")
        else:
            messagebox.showinfo("Terminado", f"PDF guardado en:\n{pdf_salida}")

    except Exception as error:
        messagebox.showerror("Error", str(error))

if __name__ == "__main__":
    ventana = Tk()
    ventana.withdraw()
    ejecutar()
    ventana.destroy()