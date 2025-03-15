import json
import os

import gpxpy
import gpxpy.gpx
import folium
from django.conf import settings
from geopy.distance import geodesic
from datetime import timedelta
from keras.src.saving import load_model
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

from django.shortcuts import render, redirect

from proyectoFinal.models import Rutas


def analizar_gpx(fichero_gpx):
    titulo = None
    fecha = None
    UMBRAL_MOVIMIENTO = 1.0
    gpx = fichero_gpx.read().decode('utf-8')
    gpx = gpxpy.parse(gpx)

    distancia_total = 0.0  # En km
    tiempo_total = timedelta(seconds=0)
    tiempo_movimiento = timedelta(seconds=0)
    tiempo_pausa = timedelta(seconds=0)

    velocidad_maxima = 0.0  # En km/h

    altitud_max = float('-inf')
    altitud_min = float('inf')
    ganancia_altitud = 0.0  # En metros
    perdida_altitud = 0.0  # En metros
    if gpx.name is not None or gpx.time is not None:
        titulo = gpx.name
        fecha = gpx.time.date()
    else:
        for track in gpx.tracks:
            titulo = track.name
            for segment in track.segments:
                for i in range(1, len(segment.points)):
                    p1 = segment.points[i - 1]
                    p2 = segment.points[i]

                    # Calcular distancia entre puntos
                    distancia = geodesic((p1.latitude, p1.longitude), (p2.latitude, p2.longitude)).km
                    distancia_total += distancia

                    # Calcular tiempo entre puntos
                    tiempo_transcurrido = (p2.time - p1.time).total_seconds()
                    tiempo_total += timedelta(seconds=tiempo_transcurrido)

                    # Calcular velocidad instantánea
                    if tiempo_transcurrido > 0:
                        velocidad = (distancia * 1000) / tiempo_transcurrido  # m/s
                        velocidad_kmh = velocidad * 3.6  # Convertir a km/h

                        # Guardar velocidad máxima
                        if velocidad_kmh > velocidad_maxima:
                            velocidad_maxima = velocidad_kmh

                        # Determinar si estaba en movimiento
                        if velocidad > UMBRAL_MOVIMIENTO:
                            tiempo_movimiento += timedelta(seconds=tiempo_transcurrido)
                        else:
                            tiempo_pausa += timedelta(seconds=tiempo_transcurrido)

                    # Cálculo de altitudes
                    if p1.elevation is not None and p2.elevation is not None:
                        altitud_max = max(altitud_max, p2.elevation)
                        altitud_min = min(altitud_min, p2.elevation)

                        diferencia_altitud = p2.elevation - p1.elevation
                        if diferencia_altitud > 0:
                            ganancia_altitud += diferencia_altitud
                        else:
                            perdida_altitud += abs(diferencia_altitud)

    # Calcular velocidad media en movimiento (km/h)
    velocidad_media = (distancia_total / (
            tiempo_movimiento.total_seconds() / 3600)) if tiempo_movimiento.total_seconds() > 0 else 0

    return {
        "titulo": titulo,
        "fecha": fecha,
        "total_km": round(distancia_total, 2),
        "tiempo_total": tiempo_total,
        "tiempo_movimiento": tiempo_movimiento,
        "tiempo_pausa": tiempo_pausa,
        "vel_media_movimiento": round(velocidad_media, 2),
        "velocidad_maxima": round(velocidad_maxima, 2),
        "altitud_maxima": round(altitud_max, 2) if altitud_max != float('-inf') else None,
        "altitud_minima": round(altitud_min, 2) if altitud_min != float('inf') else None,
        "alt_acum_max": round(ganancia_altitud, 2),
        "alt_acum_min": round(perdida_altitud, 2)
    }


def generarMapaGPX(archivo_gpx):
    # with open(archivo_gpx, 'r') as gpx_file:
    #     gpx = gpxpy.parse(gpx_file)

    gpx = archivo_gpx.read().decode('utf-8')
    gpx = gpxpy.parse(gpx)

    # Extraer los puntos de la ruta
    ruta = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                ruta.append((point.latitude, point.longitude))

    # Crear un mapa centrado en el primer punto de la ruta
    mapa = folium.Map(location=ruta[0], zoom_start=14)

    # Añadir la ruta en el mapa
    folium.PolyLine(ruta, color="blue", weight=4.5, opacity=0.8).add_to(mapa)

    # Marcar puntos de inicio y fin
    folium.Marker(ruta[0], popup="Inicio", icon=folium.Icon(color="green")).add_to(mapa)
    folium.Marker(ruta[-1], popup="Fin", icon=folium.Icon(color="red")).add_to(mapa)

    return mapa
    # Guardar el mapa en un archivo HTML
    # mapa.save("mapa_ruta.html")


def prediccionNuevaRuta(desnivel_positivo, desnivel_negativo, longitud, suelo, tipo_bici, estado):
    ruta_modelo = os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static', 'media', 'RN_TFG_v3.h5')
    modelo = load_model(ruta_modelo)

    X_new = np.array([[desnivel_positivo, desnivel_negativo, longitud, suelo, tipo_bici, estado]])

    df = pd.read_csv(os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static\media\TrainData_SinIndex.csv'))
    X = df.drop(['dificultad'], axis=1).values
    X_scaler = MinMaxScaler()
    X_scaler.fit(X)

    # Escalar los datos para la predicción
    X_new_scaled = X_scaler.transform(X_new)

    # Hacer la predicción
    y_pred = modelo.predict(X_new_scaled)
    pred_clase = int(np.argmax(y_pred, axis=1)[0])
    print("y_pred", y_pred)
    print("pred_clase", pred_clase)

    rutaDiccionario = os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static\media\diccionarios.json')

    with open(rutaDiccionario, 'r') as f:
        diccionarios_cargados = json.load(f)

    # Acceder a los diccionarios cargados
    diccionario_dif_cargado = diccionarios_cargados['dic_dificultad']
    clase = diccionario_dif_cargado.get(str(pred_clase))
    return clase


def formularioNuevaRuta(request):
    if request.method == "GET":
        if request.user.is_authenticated:
            return render(request, 'proyectofinalWeb/form_agregarRutae.html')
        else:
            return redirect('index')

    if request.method == 'POST':
        botonGuardar = request.POST.get('btnGuardar')

        if botonGuardar == 'manual':
            titulo = request.POST.get('titulo')
            fecha = request.POST.get('fecha')
            tiempo = request.POST.get('tiempo')
            distancia = request.POST.get('distancia')
            velocidad = request.POST.get('velocidad')
            ascenso = request.POST.get('ascenso')
            descenso = request.POST.get('descenso')
            ruta = Rutas(
                titulo=titulo,
                fecha=fecha,
                tiempo=tiempo,
                distancia=distancia,
                velocidad=velocidad,
                ascenso=ascenso,
                descenso=descenso,
                dureza="media",
                idUsuario=request.user
            )
            ruta.save()

            return redirect('index')

        elif botonGuardar == 'automatico':

            # Busca si esta el identificador del boton en request.FILES
            if 'ficheroGpxCsv' in request.FILES:

                # Obtiene el valor del fichero seleccionado
                fichero = request.FILES['ficheroGpxCsv']

                _, extension = os.path.splitext(fichero.name)  # Usar os.path.splitext para un mejor manejo de la extension
                extension = extension[1:].lower()
                if extension == 'gpx':
                # if fichero.split('.')[1] == 'gpx':
                    resultados = analizar_gpx(fichero)
                    mapa = generarMapaGPX(fichero)

                    ascenso_gpx = resultados.get("alt_acum_max")
                    descenso_gpx = resultados.get("alt_acum_min")
                    longitud_gpx = resultados.get("total_km")
                    # El suelo hay que cogerlo de la tabla caracteristicas usuario
                    suelo_gpx = None
                # El tipo de bici hay que cogerlo de la tabla caracteristicas usuario
                    tipo_bici_gpx = None
                # El estado del ciclista hay que cogerlo de la tabla caracteristicas usuario
                    estado_gpx = None

                    ruta_GPX = Rutas(
                        titulo=resultados.get("titulo"),
                        fecha=resultados.get("fecha"),
                        tiempo=resultados.get("tiempo_movimiento"),
                        distancia=resultados.get("total_km"),
                        velocidad=resultados.get("vel_media_movimiento"),
                        ascenso=resultados.get("alt_acum_max"),
                        descenso=resultados.get("alt_acum_min"),
                        dureza=prediccionNuevaRuta(ascenso_gpx, descenso_gpx, longitud_gpx ),
                        idUsuario=request.user
                    )

                elif fichero.split('.')[1] == 'csv':

                    # Hay que crear un nuevo metodo que llame a analizar csv

                    resultados = analizar_gpx(fichero)


def mis_rutas(request):
    if request.user.is_authenticated:
        if request.method == 'GET':
            # esAdmin = request.user.is_staff
            listaRutas = Rutas.objects.filter(idUsuario=request.user.id)
            # return render(request, 'rutase.html', {"rutas": listaRutas, "admin": esAdmin, "nombre":request.user.username})
            return render(request, 'proyectofinalWeb/rutase.html', {"rutas": listaRutas})
    else:
        return redirect('index')
