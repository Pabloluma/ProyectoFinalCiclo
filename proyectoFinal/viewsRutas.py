import io
import json
import os

import fitparse
import gpxpy
import gpxpy.gpx
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.views.decorators.http import require_POST
from geopy.distance import geodesic
from datetime import timedelta, datetime
from keras.src.saving import load_model
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

import geopandas as gpd
from shapely.geometry import LineString
import matplotlib.pyplot as plt
import contextily as ctx

from django.shortcuts import render, redirect

from proyectoFinal import views
from proyectoFinal.decorator import usuario_no_admin_requerido
from proyectoFinal.models import Rutas, graficoRuta, caracteristicas, lista

import folium

from tempfile import NamedTemporaryFile
from django.core.files import File

from geopy.distance import geodesic


def obtenerPerfil_Fit(fitfile, rutaGuardada):
    try:
        altitudes = []
        distances = []
        total_distance = 0
        previous_latitude = None
        previous_longitude = None

        # Iterar a través de los registros que contienen información de posición
        for record in fitfile.get_messages('record'):
            timestamp = record.get('timestamp')
            position_lat = record.get('position_lat')
            position_long = record.get('position_long')
            enhanced_altitude = record.get('enhanced_altitude')

            if timestamp and timestamp.value and position_lat and position_lat.value is not None and position_long and position_long.value is not None and enhanced_altitude and enhanced_altitude.value is not None:
                lat = position_lat.value * (180.0 / 2 ** 31)
                lon = position_long.value * (180.0 / 2 ** 31)
                alt = enhanced_altitude.value

                if previous_latitude is not None and previous_longitude is not None:
                    distance = geodesic((previous_latitude, previous_longitude), (lat, lon)).km
                    total_distance += distance

                altitudes.append(alt)
                distances.append(total_distance)
                previous_latitude = lat
                previous_longitude = lon

        if distances and altitudes:
            plt.figure(figsize=(16, 5), facecolor="white")
            plt.xlabel("Distancia (km)", fontsize=12)
            plt.ylabel("Altitud (m)", fontsize=12)
            plt.fill_between(distances, altitudes, color='lightgreen', alpha=0.6)
            plt.plot(distances, altitudes, color='green', linewidth=1.2)

            # Personalizar la gráfica
            plt.grid(color='lightgray', linestyle='--', linewidth=0.5)
            # Ajustar la gráfica a los ejes
            plt.xlim(min(distances), max(distances))
            plt.ylim(bottom=0)

            plt.xticks(fontsize=10)
            plt.yticks(fontsize=10)

            img_buffer = io.BytesIO()

            plt.savefig(img_buffer, format='png', dpi=700, bbox_inches='tight')

            img_buffer.seek(0)
            imagen_file = InMemoryUploadedFile(img_buffer, None, f"perfil_{rutaGuardada.id}.png", 'image/png',
                                               img_buffer.tell(), None)

            rutaGuardada.graficosRuta.gr_perfil.save(f"perfil_{rutaGuardada.id}.png", imagen_file, save=True)
            return imagen_file
        else:
            print("No se encontraron datos suficientes de posición y altitud en el archivo.")

    except FileNotFoundError:
        print("Error: El archivo  no fue encontrado.")
    except Exception as e:
        print(f"Ocurrió un error al procesar el archivo: {e}")


def obtener_mapaFit_html(fitfile, rutaGuardada):
    # Extraer puntos GPS
    ruta = []
    for record in fitfile.get_messages("record"):
        lat = record.get_value("position_lat")
        lon = record.get_value("position_long")

        if lat is not None and lon is not None:
            # Convertir de semicircles a grados
            lat = lat * (180 / 2 ** 31)
            lon = lon * (180 / 2 ** 31)
            ruta.append((lat, lon))

    # Crear el mapa si hay puntos
    if ruta:
        mapa = folium.Map(location=ruta[0], zoom_start=14)

        # Añadir la ruta
        folium.PolyLine(ruta, color="blue", weight=4.5, opacity=0.8).add_to(mapa)

        # Marcar inicio y fin
        folium.Marker(ruta[0], popup="Inicio", icon=folium.Icon(color="green")).add_to(mapa)
        folium.Marker(ruta[-1], popup="Fin", icon=folium.Icon(color="red")).add_to(mapa)

        # return mapa
        # Guardar el mapa
        # mapa.save("mapa_miFichero2.html")
        # print("Mapa generado: mapa_miFichero.html")
        with NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
            mapa.save(temp_file.name)
            temp_file.seek(0)

            # Asociar al modelo
            grafico = graficoRuta(id_ruta=rutaGuardada)  # Asumiendo que tienes la ruta
            grafico.mapa_interac.save(f"mapa_ruta_{rutaGuardada.id}.html", File(temp_file))
            grafico.save()
    else:
        print("No se encontraron puntos GPS en el archivo .fit.")


def analizar_fit(fitfile):  # (fichero_fit):
    titulo = None
    fecha = None
    UMBRAL_MOVIMIENTO = 1.0  # Ajustar según necesidad (m/s)
    distancia_total = 0.0
    tiempo_total = timedelta(seconds=0)
    tiempo_movimiento = timedelta(seconds=0)
    tiempo_pausa = timedelta(seconds=0)
    velocidad_maxima = 0.0
    altitud_max = float('-inf')
    altitud_min = float('inf')
    ganancia_altitud = 0.0
    perdida_altitud = 0.0
    puntos = []

    try:
        # fitfile = fitparse.FitFile(fichero_fit)

        # Obtener el título del archivo (si está disponible)
        for record in fitfile.get_messages('file_id'):
            for data in record:
                if data.name == 'manufacturer' and titulo is None:
                    titulo = data.value
                elif data.name == 'product' and titulo is None:
                    titulo = data.value
            if titulo:
                break

        # Recopilar puntos con timestamp, latitud, longitud y altitud
        for record in fitfile.get_messages('record'):
            timestamp = record.get('timestamp')
            position_lat = record.get('position_lat')
            position_long = record.get('position_long')
            enhanced_altitude = record.get('enhanced_altitude')

            if timestamp and timestamp.value and position_lat and position_lat.value is not None and position_long and position_long.value is not None:
                point = {
                    'time': timestamp.value,
                    'latitude': position_lat.value * (180.0 / 2 ** 31),  # Convertir semicircles a degrees
                    'longitude': position_long.value * (180.0 / 2 ** 31),  # Convertir semicircles a degrees
                    'elevation': enhanced_altitude.value if enhanced_altitude and enhanced_altitude.value is not None else None
                }
                puntos.append(point)
                if fecha is None:
                    fecha = point['time'].date()

        # Simular el análisis por segmentos como en el GPX
        if len(puntos) > 1:
            for i in range(1, len(puntos)):
                p1 = puntos[i - 1]
                p2 = puntos[i]

                distancia = geodesic((p1['latitude'], p1['longitude']), (p2['latitude'], p2['longitude'])).km
                distancia_total += distancia

                tiempo_transcurrido = (p2['time'] - p1['time']).total_seconds()
                tiempo_total += timedelta(seconds=tiempo_transcurrido)

                if tiempo_transcurrido > 0:
                    velocidad = (distancia * 1000) / tiempo_transcurrido  # m/s
                    velocidad_kmh = velocidad * 3.6  # Convertir a km/h

                    if velocidad_kmh > velocidad_maxima:
                        velocidad_maxima = velocidad_kmh

                    if velocidad > UMBRAL_MOVIMIENTO:
                        tiempo_movimiento += timedelta(seconds=tiempo_transcurrido)
                    else:
                        tiempo_pausa += timedelta(seconds=tiempo_transcurrido)

                if p1['elevation'] is not None and p2['elevation'] is not None:
                    altitud_max = max(altitud_max, p2['elevation'])
                    altitud_min = min(altitud_min, p2['elevation'])

                    diferencia_altitud = p2['elevation'] - p1['elevation']
                    if diferencia_altitud > 0:
                        ganancia_altitud += diferencia_altitud
                    else:
                        perdida_altitud += abs(diferencia_altitud)

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

    except FileNotFoundError:
        # return {"error": f"El archivo '{fichero_fit}' no fue encontrado."}
        return {"error": "El archivo no fue encontrado."}
    except Exception as e:
        return {"error": f"Ocurrió un error al procesar el archivo: {e}"}


def analizar_gpx(fichero_gpx):
    titulo = None
    fecha = None
    UMBRAL_MOVIMIENTO = 1.0
    # gpx = fichero_gpx.read().decode('utf-8')
    # gpx = gpxpy.parse(gpx)
    gpx = gpxpy.parse(fichero_gpx)
    distancia_total = 0.0
    tiempo_total = timedelta(seconds=0)
    tiempo_movimiento = timedelta(seconds=0)
    tiempo_pausa = timedelta(seconds=0)

    velocidad_maxima = 0.0

    altitud_max = float('-inf')
    altitud_min = float('inf')
    ganancia_altitud = 0.0
    perdida_altitud = 0.0
    if gpx.name is not None and gpx.time is not None:
        titulo = gpx.name
        fecha = gpx.time.date()

    if gpx.time is not None:
        fecha = gpx.time.date()

    if gpx.name is None:
        for track in gpx.tracks:
            titulo = track.name
            for segment in track.segments:
                for i in range(1, len(segment.points)):
                    p1 = segment.points[i - 1]
                    p2 = segment.points[i]

                    distancia = geodesic((p1.latitude, p1.longitude), (p2.latitude, p2.longitude)).km
                    distancia_total += distancia

                    tiempo_transcurrido = (p2.time - p1.time).total_seconds()
                    tiempo_total += timedelta(seconds=tiempo_transcurrido)

                    if tiempo_transcurrido > 0:
                        velocidad = (distancia * 1000) / tiempo_transcurrido  # m/s
                        velocidad_kmh = velocidad * 3.6  # Convertir a km/h

                        if velocidad_kmh > velocidad_maxima:
                            velocidad_maxima = velocidad_kmh

                        if velocidad > UMBRAL_MOVIMIENTO:
                            tiempo_movimiento += timedelta(seconds=tiempo_transcurrido)
                        else:
                            tiempo_pausa += timedelta(seconds=tiempo_transcurrido)

                    if p1.elevation is not None and p2.elevation is not None:
                        altitud_max = max(altitud_max, p2.elevation)
                        altitud_min = min(altitud_min, p2.elevation)

                        diferencia_altitud = p2.elevation - p1.elevation
                        if diferencia_altitud > 0:
                            ganancia_altitud += diferencia_altitud
                        else:
                            perdida_altitud += abs(diferencia_altitud)

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


def generarImagenMapaGPX(fichero_gpx, rutaGuardada):
    gpx = gpxpy.parse(fichero_gpx)

    coords = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                coords.append((point.longitude, point.latitude))

    # Convertir a GeoDataFrame
    line = LineString(coords)
    gdf = gpd.GeoDataFrame(geometry=[line], crs="EPSG:4326")
    gdf = gdf.to_crs(epsg=3857)  # Web Mercator para contextily

    # Crear imagen en memoria
    fig, ax = plt.subplots(figsize=(10, 5))
    gdf.plot(ax=ax, linewidth=2, color='blue')
    ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)

    xmin, xmax = ax.get_xlim()
    ancho_figura = fig.get_figwidth()
    extension_longitud = (xmax - xmin) * (3 / ancho_figura)  # Aproximación de 3 pulgadas en longitud

    xmin_extendido = xmin - extension_longitud
    xmax_extendido = xmax + extension_longitud

    # Establecer los límites extendidos del eje x
    ax.set_xlim(xmin_extendido, xmax_extendido)

    ax.axis("off")

    img_buffer = io.BytesIO()

    plt.savefig(img_buffer, format='png', dpi=700, bbox_inches='tight')
    plt.close(fig)

    img_buffer.seek(0)
    imagen_file = InMemoryUploadedFile(img_buffer, None, f"i_mapa_ruta_g_{rutaGuardada.id}.png", 'image/png',
                                       img_buffer.tell(), None)
    rutaGuardada.imagen.save(f"mapas/i_mapa_ruta_{rutaGuardada.id}.png", imagen_file, save=True)


# def generarImagenMapaFIT(fichero_fit, rutaGuardada):
def generarImagenMapaFIT(fitfile, rutaGuardada):
    try:
        # fitfile = fitparse.FitFile(fichero_fit)

        coords = []
        for record in fitfile.get_messages('record'):
            position_lat = record.get('position_lat')
            position_long = record.get('position_long')

            if position_lat and position_lat.value is not None and position_long and position_long.value is not None:
                lat = position_lat.value * (180.0 / 2 ** 31)
                lon = position_long.value * (180.0 / 2 ** 31)
                coords.append((lon, lat))

        if coords:
            # Convertir a GeoDataFrame
            line = LineString(coords)
            gdf = gpd.GeoDataFrame(geometry=[line], crs="EPSG:4326")
            gdf = gdf.to_crs(epsg=3857)  # Web Mercator para contextily

            # Crear imagen en memoria
            fig, ax = plt.subplots(figsize=(10, 5))
            gdf.plot(ax=ax, linewidth=2, color='blue')
            ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)

            xmin, xmax = ax.get_xlim()
            ancho_figura = fig.get_figwidth()  # Ancho de la figura en pulgadas
            extension_longitud = (xmax - xmin) * (3 / ancho_figura)  # Aproximación de 3 pulgadas en longitud

            xmin_extendido = xmin - extension_longitud
            xmax_extendido = xmax + extension_longitud

            # Establecer los límites extendidos del eje x
            ax.set_xlim(xmin_extendido, xmax_extendido)

            ax.axis("off")

            img_buffer = io.BytesIO()

            plt.savefig(img_buffer, format='png', dpi=700, bbox_inches='tight')
            plt.close(fig)

            img_buffer.seek(0)
            imagen_file = InMemoryUploadedFile(img_buffer, None, f"i_mapa_ruta_f_{rutaGuardada.id}.png", 'image/png',
                                               img_buffer.tell(), None)
            rutaGuardada.imagen.save(f"mapas/i_mapa_ruta_{rutaGuardada.id}.png", imagen_file, save=True)
            return imagen_file
        else:
            print("No se encontraron datos de latitud y longitud en el archivo .fit.")
            return None

    except FileNotFoundError:
        print("Error: No se ha podido encontrar el Archivo")
        return None
    except ImportError as e:
        print(
            f"Error: No se pudo importar una librería necesaria: {e}. Asegúrate de tener instaladas fitparse, geopandas y contextily (pip install fitparse geopandas contextily).")
        return None
    except Exception as e:
        print(f"Ocurrió un error al procesar el archivo .fit: {e}")
        return None


def generarMapaGPX_HTML(fichero_gpx):
    gpx = gpxpy.parse(fichero_gpx)

    ruta = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                ruta.append((point.latitude, point.longitude))

    mapa = folium.Map(location=ruta[0], zoom_start=14)

    # Añadir la ruta en el mapa
    folium.PolyLine(ruta, color="blue", weight=4.5, opacity=0.8).add_to(mapa)

    # Marcar puntos de inicio y fin
    folium.Marker(ruta[0], popup="Inicio", icon=folium.Icon(color="green")).add_to(mapa)
    folium.Marker(ruta[-1], popup="Fin", icon=folium.Icon(color="red")).add_to(mapa)

    return mapa


def prediccionNuevaRuta(desnivel_positivo, desnivel_negativo, longitud, suelo, tipo_bici, estado):
    ruta_modelo = os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static', 'ficheros', 'RN_TFG_v3.h5')
    modelo = load_model(ruta_modelo)

    X_new = np.array([[desnivel_positivo, desnivel_negativo, longitud, suelo, tipo_bici, estado]])

    df = pd.read_csv(os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static\\ficheros\TrainData_SinIndex.csv'))
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

    rutaDiccionario = os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static\\ficheros\diccionarios.json')

    with open(rutaDiccionario, 'r') as f:
        diccionarios_cargados = json.load(f)

    # Acceder a los diccionarios cargados
    diccionario_dif_cargado = diccionarios_cargados['dic_dificultad']
    clase = diccionario_dif_cargado.get(str(pred_clase))
    return clase


def obtenerRitmos_Fit(fitfile, rutaGuardada):
    try:
        distancias = []
        ritmos_cardiacos = []
        cadencias = []
        temperaturas = []

        distancia_acumulada = 0.0

        for record in fitfile.get_messages('record'):
            distancia = record.get('distance')
            ritmo_cardiaco = record.get('heart_rate')
            cadencia = record.get('cadence')
            temperatura = record.get('temperature')

            if distancia and distancia.value is not None:
                distancia_acumulada = distancia.value / 1000.0  # distancia en km
                distancias.append(distancia_acumulada)

                if ritmo_cardiaco and ritmo_cardiaco.value is not None:
                    ritmos_cardiacos.append(ritmo_cardiaco.value)
                else:
                    ritmos_cardiacos.append(None)

                if cadencia and cadencia.value is not None:
                    cadencias.append(cadencia.value)
                else:
                    cadencias.append(None)

                if temperatura and temperatura.value is not None:
                    temperaturas.append(temperatura.value)
                else:
                    temperaturas.append(None)

        # Gráfico de ritmo cardíaco
        plt.figure(figsize=(10, 5))
        plt.plot(distancias, ritmos_cardiacos, label='Ritmo Cardíaco (bpm)')
        plt.xlabel('Distancia (km)')
        plt.ylabel('Ritmo Cardíaco (bpm)')
        plt.title('Ritmo Cardíaco por Distancia')
        plt.legend()
        plt.grid(True)
        # Personalización del eje x
        max_distancia = max(distancias)
        ticks = np.arange(0, max_distancia + 10, 10)  # Crear ticks de 10 en 10
        plt.xticks(ticks)
        # plt.savefig("frecCard.png", dpi=300)
        # plt.show()
        # Guardar en memoria
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        imagen_file = InMemoryUploadedFile(img_buffer, None, f"ppm_{rutaGuardada.id}.png", 'image/png',
                                           img_buffer.tell(), None)
        rutaGuardada.graficosRuta.gr_pulsaciones.save(f"ppm_{rutaGuardada.id}.png", imagen_file, save=True)
        plt.close()

        # Gráfico de cadencia
        plt.figure(figsize=(10, 5))
        plt.plot(distancias, cadencias, label='Cadencia (rpm)')
        plt.xlabel('Distancia (km)')
        plt.ylabel('Cadencia (rpm)')
        plt.title('Cadencia por Distancia')
        plt.legend()
        plt.grid(True)
        # Personalización del eje x
        plt.xticks(ticks)
        # plt.show()
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        imagen_file = InMemoryUploadedFile(img_buffer, None, f"rpm_{rutaGuardada.id}.png", 'image/png',
                                           img_buffer.tell(), None)
        rutaGuardada.graficosRuta.gr_cadencia.save(f"rpm_{rutaGuardada.id}.png", imagen_file, save=True)
        plt.close()

        # Gráfico de temperatura
        plt.figure(figsize=(10, 5))
        plt.plot(distancias, temperaturas, label='Temperatura (°C)')
        plt.xlabel('Distancia (km)')
        plt.ylabel('Temperatura (°C)')
        plt.title('Temperatura por Distancia')
        plt.legend()
        plt.grid(True)
        plt.xticks(ticks)
        # plt.show()
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        imagen_file = InMemoryUploadedFile(img_buffer, None, f"temperatura_{rutaGuardada.id}.png", 'image/png',
                                           img_buffer.tell(), None)
        rutaGuardada.graficosRuta.gr_temperatura.save(f"temperatura_{rutaGuardada.id}.png", imagen_file, save=True)
        plt.close()

    except Exception as e:
        print(f"Error al procesar el archivo: {e}")


@usuario_no_admin_requerido
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
            # tiempo = request.POST.get('tiempo')
            distancia = request.POST.get('distancia')
            velocidad = request.POST.get('velocidad')
            ascenso = request.POST.get('ascenso')
            descenso = request.POST.get('descenso')
            visibilidad = request.POST.get('visibilidad')

            # --- MODIFICACIÓN CLAVE PARA EL TIEMPO ---
            # Obtener las partes separadas del tiempo
            horas_str = request.POST.get('horas', '0')
            minutos_str = request.POST.get('minutos', '0')
            segundos_str = request.POST.get('segundos', '0')

            # Convertir a enteros y manejar posibles errores (fundamental para la conversión)
            try:
                horas = int(horas_str)
                minutos = int(minutos_str)
                segundos = int(segundos_str)
            except ValueError:
                # Si no son números válidos, se asumirá 0 para la conversión
                horas, minutos, segundos = 0, 0, 0

            # Convertir a objeto datetime.time (para models.TimeField)
            # Esto maneja el desbordamiento de 24 horas: 25h se convierte en 01:00:00
            total_seconds_duration = horas * 3600 + minutos * 60 + segundos
            tiempo_obj = (datetime.min + timedelta(seconds=total_seconds_duration)).time()
            # El suelo hay que cogerlo de la tabla caracteristicas usuario
            # suelo_usuario = '1'
            # # El tipo de bici hay que cogerlo de la tabla caracteristicas usuario
            # tipo_bici_usuario = '1'
            # # El estado del ciclista hay que cogerlo de la tabla caracteristicas usuario
            # estado_usuario = '1'
            usuario_log = request.user
            caracteristicasUsuario = usuario_log.caracteristicas
            if caracteristicasUsuario:
                suelo_usuario = caracteristicasUsuario.suelo
                # El tipo de bici hay que cogerlo de la tabla caracteristicas usuario
                tipo_bici_usuario = caracteristicasUsuario.tipo_bici
                # El estado del ciclista hay que cogerlo de la tabla caracteristicas usuario
                estado_usuario = caracteristicasUsuario.estado
            else:
                suelo_usuario = '1'
                # El tipo de bici hay que cogerlo de la tabla caracteristicas usuario
                tipo_bici_usuario = '1'
                # El estado del ciclista hay que cogerlo de la tabla caracteristicas usuario
                estado_usuario = '1'
            pred_manual = prediccionNuevaRuta(desnivel_positivo=ascenso, desnivel_negativo=descenso,
                                              longitud=distancia, suelo=suelo_usuario, tipo_bici=tipo_bici_usuario,
                                              estado=estado_usuario)
            ruta = Rutas(
                titulo=titulo,
                fecha=fecha,
                tiempo=tiempo_obj,
                distancia=distancia,
                velocidad=velocidad,
                ascenso=ascenso,
                descenso=descenso,
                dureza=pred_manual,
                tipoFichero='M',
                # publico=True if pred_manual == '1' else False,
                publico=True if visibilidad == '1' else False,
                idUsuario=request.user
            )
            ruta.save()

            return redirect('index')

        elif botonGuardar == 'automatico':

            # Busca si esta el identificador del boton en request.FILES
            if 'ficheroGpxCsv' in request.FILES:

                # Obtiene el valor del fichero seleccionado
                fichero = request.FILES['ficheroGpxCsv']

                _, extension = os.path.splitext(fichero.name)
                extension = extension[1:].lower()
                if extension == 'gpx':
                    fichero_leido = fichero.read().decode('utf-8')
                    resultados = analizar_gpx(fichero_leido)
                    ascenso_gpx = resultados.get("alt_acum_max")
                    descenso_gpx = resultados.get("alt_acum_min")
                    longitud_gpx = resultados.get("total_km")
                    # El suelo hay que cogerlo de la tabla caracteristicas usuario
                    # suelo_gpx = '1'
                    # # El tipo de bici hay que cogerlo de la tabla caracteristicas usuario
                    # tipo_bici_gpx = '1'
                    # # El estado del ciclista hay que cogerlo de la tabla caracteristicas usuario
                    # estado_gpx = '1'
                    usuario_log = request.user
                    caracteristicasUsuario = usuario_log.caracteristicas
                    if caracteristicasUsuario:
                        suelo_gpx = caracteristicasUsuario.suelo

                        tipo_bici_gpx = caracteristicasUsuario.tipo_bici

                        estado_gpx = caracteristicasUsuario.estado
                    else:
                        suelo_gpx = '1'
                        # El tipo de bici hay que cogerlo de la tabla caracteristicas usuario
                        tipo_bici_gpx = '1'
                        # El estado del ciclista hay que cogerlo de la tabla caracteristicas usuario
                        estado_gpx = '1'
                    pred = prediccionNuevaRuta(desnivel_positivo=ascenso_gpx, desnivel_negativo=descenso_gpx,
                                               longitud=longitud_gpx, suelo=suelo_gpx, tipo_bici=tipo_bici_gpx,
                                               estado=estado_gpx)

                    ruta_GPX = Rutas(
                        titulo=resultados.get("titulo"),
                        fecha=str(resultados.get("fecha")),
                        tiempo=str(resultados.get("tiempo_movimiento")),
                        distancia=resultados.get("total_km"),
                        velocidad=resultados.get("vel_media_movimiento"),
                        ascenso=resultados.get("alt_acum_max"),
                        descenso=resultados.get("alt_acum_min"),
                        tipoFichero='G',
                        publico=False,
                        dureza=pred,
                        idUsuario=request.user
                    )
                    ruta_GPX.save()
                    rutaGuardada = Rutas.objects.get(id=ruta_GPX.id)
                    try:
                        generarImagenMapaGPX(fichero_leido, rutaGuardada)
                    except:
                        print("No se ha podido generar mapa")
                        mapa = None
                    return redirect('misRutas')

                elif extension == 'fit':
                    fitfile = fitparse.FitFile(fichero)
                    resultados = analizar_fit(fitfile)
                    ascenso_gpx = resultados.get("alt_acum_max")
                    descenso_gpx = resultados.get("alt_acum_min")
                    longitud_gpx = resultados.get("total_km")
                    # El suelo hay que cogerlo de la tabla caracteristicas usuario
                    usuario_log = request.user
                    caracteristicasUsuario = usuario_log.caracteristicas
                    if caracteristicasUsuario:
                        suelo_gpx = caracteristicasUsuario.suelo
                        # El tipo de bici hay que cogerlo de la tabla caracteristicas usuario
                        tipo_bici_gpx = caracteristicasUsuario.tipo_bici
                        # El estado del ciclista hay que cogerlo de la tabla caracteristicas usuario
                        estado_gpx = caracteristicasUsuario.estado
                    else:
                        suelo_gpx = '1'
                        # El tipo de bici hay que cogerlo de la tabla caracteristicas usuario
                        tipo_bici_gpx = '1'
                        # El estado del ciclista hay que cogerlo de la tabla caracteristicas usuario
                        estado_gpx = '1'
                    pred = prediccionNuevaRuta(desnivel_positivo=ascenso_gpx, desnivel_negativo=descenso_gpx,
                                               longitud=longitud_gpx, suelo=suelo_gpx, tipo_bici=tipo_bici_gpx,
                                               estado=estado_gpx)

                    ruta_GPX = Rutas(
                        titulo=resultados.get("titulo"),
                        fecha=str(resultados.get("fecha")),
                        tiempo=str(resultados.get("tiempo_movimiento")),
                        distancia=resultados.get("total_km"),
                        velocidad=resultados.get("vel_media_movimiento"),
                        ascenso=resultados.get("alt_acum_max"),
                        descenso=resultados.get("alt_acum_min"),
                        dureza=pred,
                        tipoFichero='F',
                        publico=False,
                        # imagen=mapa,
                        idUsuario=request.user
                    )
                    ruta_GPX.save()
                    rutaGuardada = Rutas.objects.get(id=ruta_GPX.id)
                    try:
                        generarImagenMapaFIT(fitfile, rutaGuardada)
                        obtener_mapaFit_html(fitfile, rutaGuardada)
                        obtenerPerfil_Fit(fitfile, rutaGuardada)
                        obtenerRitmos_Fit(fitfile, rutaGuardada)
                    except:
                        print("No se ha podido generar mapa")
                        mapa = None
                    return redirect('misRutas')


@usuario_no_admin_requerido
def mis_rutas(request):
    if request.user.is_authenticated:
        if request.method == 'GET':
            listaRutas = Rutas.objects.filter(idUsuario=request.user.id).prefetch_related("comentarios").order_by(
                "fechaSubida").reverse()
            for r in listaRutas:
                r.diferencia = views.diferenciaTiempo(r.fechaSubida)
            return render(request, 'proyectofinalWeb/rutase.html', {"rutas": listaRutas})
    else:
        return redirect('index')


def detalles_ruta(request, id_ruta):
    referer = request.META.get('HTTP_REFERER', '')
    if '/misRutas' not in referer and '/inicio' not in referer:
        return redirect('misRutas')
    try:
        ruta = Rutas.objects.get(pk=id_ruta)
        listaComentarios = ruta.comentarios.all()
        try:
            listaGraficos = graficoRuta.objects.get(id_ruta=ruta)
            graficos = {
                'Perfil': listaGraficos.gr_perfil,
                'Pulsaciones': listaGraficos.gr_pulsaciones,
                'Cadencia': listaGraficos.gr_cadencia,
                'Temperatura': listaGraficos.gr_temperatura,
            }
        except:
            return render(request, "proyectofinalWeb/detallesRutas.html",
                          {'rutaSelec': ruta, 'listaComentarios': listaComentarios})

        return render(request, "proyectofinalWeb/detallesRutas.html",
                      {'rutaSelec': ruta, 'graficos': listaGraficos, 'listaComentarios': listaComentarios,
                       "imagenes": graficos})
    except Rutas.DoesNotExist:
        messages.success(request, "La ruta no existe", extra_tags="ruta_error")


@usuario_no_admin_requerido
# @require_POST
def visibilidad(request):
    if request.method == "POST":
        id_ruta = request.POST.get('id_ruta')
        ruta_cambiar = Rutas.objects.get(pk=id_ruta)
        cambiar_a = request.POST.get('publico') == 'True'
        ruta_cambiar.publico = cambiar_a
        ruta_cambiar.save()
        estado = "pública" if cambiar_a else "privada"
        messages.success(request, f"La ruta ahora es {estado}.", extra_tags="cambio_permiso")
        return redirect('misRutas')
    else:
        return render(request, "error/405.html", status=405)


# @require_POST
def eliminarRuta(request):
    if request.method == "POST":
        id_ruta = request.POST.get('id_ruta_eliminar')
        ruta_eliminar = Rutas.objects.get(pk=id_ruta)
        ruta_eliminar.delete()
        messages.success(request, f"La ruta se ha eliminado correctamente", extra_tags="eliminar_Ruta")
        return redirect('misRutas')
    else:
        return render(request, "error/405.html", status=405)


def eliminarVideo(request):
    if request.method == "POST":
        id_lista = request.POST.get('id_video_eliminar')
        lista_eliminar = lista.objects.get(pk=id_lista)
        lista_eliminar.delete()
        messages.success(request, f"La lista se ha eliminado correctamente", extra_tags="eliminar_lista")
        return redirect('misRutas')
    else:
        return render(request, "error/405.html", status=405)


def eliminarUsuario(request):
    if request.method == "POST":
        id_usuario = request.POST.get('id_usuario_eliminar')
        usuario_eliminar = User.objects.get(pk=id_usuario)
        usuario_eliminar.delete()
        messages.success(request, f"El usuario se ha eliminado correctamente", extra_tags="eliminar_Usuario")
        return redirect('administracion')
    else:
        return render(request, "error/405.html", status=405)
