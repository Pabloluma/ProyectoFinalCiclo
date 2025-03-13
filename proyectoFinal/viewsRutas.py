import gpxpy
import gpxpy.gpx
import folium
from geopy.distance import geodesic
from datetime import timedelta

from django.shortcuts import render, redirect

from proyectoFinal.models import Rutas


def analizar_gpx(fichero_gpx):
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

    for track in gpx.tracks:
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
        elif botonGuardar == 'automatico':
            if 'ficheroGpxCsv' in request.FILES:
                fichero = request.FILES['ficheroGpxCsv']
                if fichero.split('.')[1] == 'gpx':
                    resultados = analizar_gpx(fichero)
                    return
                elif fichero.split('.')[1] == 'csv':
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
