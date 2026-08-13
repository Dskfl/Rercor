import cv2
import numpy as np
import os
from pathlib import Path
from tkinter import Tk, filedialog, messagebox, Toplevel, Button, Label
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from rembg import remove
from datetime import datetime

# ============================================================
# CONSTANTES Y CONFIGURACIÓN
# ============================================================
OUTPUT_WIDTH = 2400 
PROPORCION = 54.0 / 85.6 

def mm_to_points(mm):
    return mm * 72 / 25.4

# ============================================================
# PROCESAMIENTO
# ============================================================
def ordenar_puntos(puntos):
    puntos = np.array(puntos, dtype=np.float32)
    suma = puntos.sum(axis=1)
    diferencia = np.diff(puntos, axis=1).reshape(-1)
    return np.array([
        puntos[np.argmin(suma)], puntos[np.argmin(diferencia)], 
        puntos[np.argmax(suma)], puntos[np.argmax(diferencia)]
    ], dtype=np.float32)

def detectar_con_ia(imagen):
    alto, ancho = imagen.shape[:2]
    max_dim = 1200
    escala = 1
    if max(alto, ancho) > max_dim:
        escala = max_dim / max(alto, ancho)
        img_procesar = cv2.resize(imagen, (int(ancho * escala), int(alto * escala)), interpolation=cv2.INTER_AREA)
    else:
        img_procesar = imagen.copy()

    img_rgb = cv2.cvtColor(img_procesar, cv2.COLOR_BGR2RGB)
    img_sin_fondo = remove(img_rgb)
    mascara = img_sin_fondo[:, :, 3] 
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos: return None
    contorno_max = max(contornos, key=cv2.contourArea)
    rectangulo = cv2.minAreaRect(contorno_max)
    return ordenar_puntos(cv2.boxPoints(rectangulo)) / escala

def recortar_cedula(imagen, esquinas):
    ancho_salida = OUTPUT_WIDTH
    alto_salida = int(ancho_salida * PROPORCION)
    destino = np.array([[0, 0], [ancho_salida - 1, 0], [ancho_salida - 1, alto_salida - 1], [0, alto_salida - 1]], dtype=np.float32)
    matriz = cv2.getPerspectiveTransform(esquinas, destino)
    return cv2.warpPerspective(imagen, matriz, (ancho_salida, alto_salida), flags=cv2.INTER_LANCZOS4)

def procesar_foto(ruta, salida, tipo_cara, a_color=True):
    imagen = cv2.imread(str(ruta))
    esquinas = detectar_con_ia(imagen)
    if esquinas is None:
        messagebox.showwarning("Aviso", f"IA falló en {tipo_cara}. Usa el mouse.")
        roi = cv2.selectROI(f"Selecciona {tipo_cara}", imagen, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow(f"Selecciona {tipo_cara}")
        x, y, w, h = roi
        esquinas = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.float32)
    
    resultado = recortar_cedula(imagen, esquinas)
    if not a_color:
        resultado = cv2.cvtColor(cv2.cvtColor(resultado, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    cv2.imwrite(str(salida), resultado, [cv2.IMWRITE_PNG_COMPRESSION, 1])

# ============================================================
# CREAR PDF MULTIPÁGINA PARA LOTES
# ============================================================
def crear_pdf_lote(pares_imagenes, archivo_pdf, usar_tamanio_grande):
    ancho_pagina, alto_pagina = letter 
    margin = 36 
    
    if usar_tamanio_grande:
        img_width = ancho_pagina - (margin * 2)
    else:
        img_width = mm_to_points(87.0)
    
    img_height = img_width * PROPORCION
    pdf = canvas.Canvas(str(archivo_pdf), pagesize=letter)
    x_pos = (ancho_pagina - img_width) / 2
    
    y_frente = alto_pagina - margin - img_height
    y_reverso = y_frente - 30 - img_height
    
    total = len(pares_imagenes)
    for i, (frente, reverso) in enumerate(pares_imagenes):
        pdf.drawImage(str(frente), x_pos, y_frente, width=img_width, height=img_height)
        pdf.drawImage(str(reverso), x_pos, y_reverso, width=img_width, height=img_height)
        
        # Si hay más cédulas, crear una página nueva en el PDF
        if i < total - 1:
            pdf.showPage()
            
    pdf.save()

# ============================================================
# FLUJO PRINCIPAL POR LOTES
# ============================================================
def ejecutar():
    ventana = Tk()
    ventana.withdraw()
    
    color = messagebox.askyesno("Color", "¿Imprimir a COLOR?")
    es_grande = messagebox.askyesno("Tamaño", "¿Deseas imprimir en TAMAÑO GRANDE (ancho de hoja) o ORIGINAL (8.7 cm)?")
    
    # 1. Seleccionar todos los frentes a la vez
    frentes = filedialog.askopenfilenames(title="1. Selecciona TODOS los FRENTES (Usa Ctrl para elegir varios)")
    if not frentes: return
    
    # 2. Seleccionar todos los reversos a la vez
    reversos = filedialog.askopenfilenames(title="2. Selecciona TODOS los REVERSOS (En el mismo orden que los frentes)")
    if not reversos: return
    
    if len(frentes) != len(reversos):
        messagebox.showerror("Error", f"La cantidad de Frentes ({len(frentes)}) no coincide con la cantidad de Reversos ({len(reversos)}). Deben ser iguales.")
        ventana.destroy()
        return

    try:
        carpeta = Path.home() / "OneDrive" / "Desktop" / "salida_cedulas"
        carpeta.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_salida = carpeta / f"cedulas_lote_{timestamp}.pdf"
        
        pares_procesados = []
        
        for i, (f_ruta, r_ruta) in enumerate(zip(frentes, reversos)):
            f_salida = carpeta / f"frente_{timestamp}_{i}.png"
            r_salida = carpeta / f"reverso_{timestamp}_{i}.png"
            
            procesar_foto(f_ruta, f_salida, f"FRENTE #{i+1}", a_color=color)
            procesar_foto(r_ruta, r_salida, f"REVERSO #{i+1}", a_color=color)
            
            pares_procesados.append((f_salida, r_salida))
        
        crear_pdf_lote(pares_procesados, pdf_salida, es_grande)

        sub = Toplevel(ventana)
        sub.title("PDF por Lotes Generado")
        Label(sub, text=f"¡Se procesaron {len(pares_procesados)} cédulas con éxito en un solo PDF!", pady=20, padx=20).pack()
        Button(sub, text="Imprimir (Predeterminada)", command=lambda: [os.startfile(str(pdf_salida), "print"), ventana.destroy()]).pack(pady=5)
        Button(sub, text="Elegir Impresora (Manual)", command=lambda: [os.startfile(str(pdf_salida)), ventana.destroy()]).pack(pady=5)
        sub.mainloop()
    except Exception as e:
        messagebox.showerror("Error", f"Error al procesar el lote:\n{e}")
    ventana.destroy()

if __name__ == "__main__":
    ejecutar()