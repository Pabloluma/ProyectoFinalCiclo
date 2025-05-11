import io
import json
import os

import fitparse
import gpxpy
import gpxpy.gpx
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import HttpRequest
from geopy.distance import geodesic
from datetime import timedelta
from keras.src.saving import load_model
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

import geopandas as gpd
from shapely.geometry import LineString
import matplotlib.pyplot as plt
import contextily as ctx

from django.shortcuts import render, redirect
from tensorflow.python.ops.metrics_impl import false_negatives

from proyectoFinal import views
from proyectoFinal.decorator import usuario_no_admin_requerido
from proyectoFinal.models import Rutas

from fitparse import FitFile
import folium


def obtener_mapaFit_html(archivo_fit):
    fitfile = FitFile(archivo_fit)

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

        return mapa
        # Guardar el mapa
        # mapa.save("mapa_miFichero2.html")
        # print("Mapa generado: mapa_miFichero.html")
    else:
        print("No se encontraron puntos GPS en el archivo .fit.")


def analizar_fit(fitfile):  #(fichero_fit):
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
    gdf.plot(ax=ax, linewidth=3, color='blue')
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
    imagen_file = InMemoryUploadedFile(img_buffer, None, f"i_mapa_ruta_g_{rutaGuardada.id}.png", 'image/png',
                                       img_buffer.tell(), None)
    rutaGuardada.imagen.save(f"mapas/i_mapa_ruta_g_{rutaGuardada.id}.png", imagen_file, save=True)


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
            gdf.plot(ax=ax, linewidth=3, color='blue')
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
            rutaGuardada.imagen.save(f"mapas/i_mapa_ruta_f_{rutaGuardada.id}.png", imagen_file, save=True)
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
    # Guardar el mapa en un archivo HTML
    # mapa.save("mapa_ruta.html")


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
            tiempo = request.POST.get('tiempo')
            distancia = request.POST.get('distancia')
            velocidad = request.POST.get('velocidad')
            ascenso = request.POST.get('ascenso')
            descenso = request.POST.get('descenso')
            visibilidad = request.POST.get('visibilidad')
            # El suelo hay que cogerlo de la tabla caracteristicas usuario
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
                tiempo=tiempo,
                distancia=distancia,
                velocidad=velocidad,
                ascenso=ascenso,
                descenso=descenso,
                dureza=pred_manual,
                publico=True if pred_manual == '1' else False,
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
                        idUsuario=request.user
                    )
                    ruta_GPX.save()
                    rutaGuardada = Rutas.objects.get(id=ruta_GPX.id)
                    try:
                        generarImagenMapaGPX(fichero_leido, rutaGuardada)
                        # request.session['dato'] = 'gpx'
                    except:
                        print("No se ha podido generar mapa")
                        mapa = None
                    return redirect('misRutas')

                # elif fichero.split('.')[1] == 'csv':
                #
                #     # Hay que crear un nuevo metodo que llame a analizar csv
                #
                #     resultados = analizar_gpx(fichero)
                elif extension == 'fit':
                    fitfile = fitparse.FitFile(fichero)
                    resultados = analizar_fit(fitfile)
                    ascenso_gpx = resultados.get("alt_acum_max")
                    descenso_gpx = resultados.get("alt_acum_min")
                    longitud_gpx = resultados.get("total_km")
                    # El suelo hay que cogerlo de la tabla caracteristicas usuario
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
                        # imagen=mapa,
                        idUsuario=request.user
                    )
                    ruta_GPX.save()
                    rutaGuardada = Rutas.objects.get(id=ruta_GPX.id)
                    try:
                        generarImagenMapaFIT(fitfile, rutaGuardada)
                        # request.session['dato'] = 'fit'
                    except:
                        print("No se ha podido generar mapa")
                        mapa = None
                    return redirect('misRutas')


@usuario_no_admin_requerido
def mis_rutas(request):
    if request.user.is_authenticated:
        if request.method == 'GET':
            listaRutas = Rutas.objects.filter(idUsuario=request.user.id).prefetch_related("comentarios")
            for r in listaRutas:
                r.diferencia = views.diferenciaTiempo(r.fechaSubida)
                encontrado = False
                if r.imagen:
                    nombre_completo = r.imagen.url.split('/')[-1]
                    partes_nombre = nombre_completo.split('_')
                    for i in partes_nombre:
                        if i == 'f':
                            encontrado = True
                            break
                    r.con_f = encontrado
            return render(request, 'proyectofinalWeb/rutase.html', {"rutas": listaRutas})
    else:
        return redirect('index')


def detalles_ruta(request, id_ruta):
    referer = request.META.get('HTTP_REFERER', '')
    if not referer.startswith(request.build_absolute_uri('/misRutas/')):
        return redirect('misRutas')
    try:
        ruta = Rutas.objects.get(pk=id_ruta)
        return render(request, "proyectofinalWeb/detallesRutas.html", {'idRuta': ruta.id})
    except Rutas.DoesNotExist:
        return render(request, "proyectofinalWeb/error_ruta_no_encontrada.html", status=404)
