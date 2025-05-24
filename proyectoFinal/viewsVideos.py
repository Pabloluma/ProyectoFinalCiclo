from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404
from googleapiclient.discovery import build
from .models import lista
from pytubefix import YouTube
import os
from pathlib import Path

YOUTUBE_API_KEY = 'AIzaSyDkdiJSJR8jnJSbvsIV3FSAClVxXPQ66vM'


def get_downloads_folder():
    """
    Intenta obtener la ruta a la carpeta de "Descargas" del usuario de forma multiplataforma.
    Si no se puede determinar, retorna el directorio de trabajo actual.
    """
    # Opción 1: Usando Path.home() (Funciona bien en Linux/macOS y a menudo en Windows)
    try:
        downloads_path = Path.home() / "Downloads"
        if downloads_path.is_dir():
            return downloads_path
    except Exception:
        pass  # Ignorar errores y probar otras opciones

    # Opción 2: Específico para Windows, usando USERPROFILE
    if os.name == 'nt':  # 'nt' es el nombre para Windows
        try:
            user_profile = os.environ.get('USERPROFILE')
            if user_profile:
                downloads_path = Path(user_profile) / "Downloads"
                if downloads_path.is_dir():
                    return downloads_path
        except Exception:
            pass

    # Fallback si ninguna de las opciones anteriores funcionó
    # (por ejemplo, si la carpeta "Downloads" no existe o hay un sistema inusual)
    print(
        "Advertencia: No se pudo determinar la carpeta de 'Descargas' del usuario. El archivo se guardará en el directorio de trabajo actual.")
    return Path.cwd()  # Retorna el directorio de trabajo actual como último recurso


def descargar_videos(video_url):
    try:
        # 1. Obtener la carpeta de descargas
        target_folder = get_downloads_folder()

        # Asegurarse de que la carpeta de destino exista (crearla si es necesario)
        target_folder.mkdir(parents=True, exist_ok=True)

        # 2. Inicializar el objeto YouTube
        yt = YouTube(video_url)

        # 3. Seleccionar la mejor resolución (o el stream que prefieras)
        ys = yt.streams.get_highest_resolution()

        # 4. Obtener el título del video para información y nombre de archivo (pytube lo sanea automáticamente)
        video_title = yt.title

        print(f"Descargando '{video_title}' en: {target_folder}")

        # 5. Descargar el video a la carpeta especificada
        # El método .download() de pytube saneará el nombre del archivo automáticamente.
        ys.download(output_path=str(target_folder))

        print("¡Descarga completada con éxito!")
        # return HttpResponse("¡Descarga completada con éxito!")
        return JsonResponse({'status': 'success', 'message': f'"{video_title}" descargado con éxito.'})
    except Exception as e:
        print(f"¡Ha ocurrido un error durante la descarga! Error: {e}")
        # return HttpResponse(f"¡Ha ocurrido un error durante la descarga! Error: {e}", status=500)
        return JsonResponse({'status': 'error', 'message': f'Error al descargar el video: {e}'}, status=500)


def obtener_todasLista(playlist_id):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    playlist_req = youtube.playlists().list(part='snippet', id=playlist_id).execute()
    item = playlist_req['items'][0]
    snippet = item['snippet']
    return {
        'id': playlist_id,
        'title': snippet['title'],
        'description': snippet.get('description', ''),
        'thumbnail': snippet['thumbnails']['high']['url'],
    }


def obtener_videos(playlist_id):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.playlistItems().list(part='snippet', playlistId=playlist_id, maxResults=50)
    response = request.execute()

    videos = []
    for item in response['items']:
        snippet = item['snippet']
        video_id = snippet['resourceId']['videoId']
        videos.append({
            'video_id': video_id,
            'title': snippet['title'],
            'description': snippet.get('description', ''),
            'thumbnail': snippet['thumbnails']['high']['url'],
            'url': f'https://www.youtube.com/watch?v={video_id}',
        })
    return videos


def cargarVideos(request, playlist_id):
    if request.method == 'POST':
        video_url = request.POST.get('video_url')
        if video_url:
            return descargar_videos(video_url)
        else:
            return JsonResponse({'status': 'error', 'message': 'No se proporcionó la URL del video'}, status=400)
    videos = obtener_videos(playlist_id)
    titulo_lista = obtener_todasLista(playlist_id).get('title')
    return render(request, 'proyectofinalWeb/videos.html',
                  {'videos': videos, 'playlist_id': playlist_id, 'titulo_lista': titulo_lista})


def cargarListas(request):
    playlist_objs = lista.objects.all()
    playlists = []
    for obj in playlist_objs:
        datos = obtener_todasLista(obj.nombre)
        playlists.append(datos)

    return render(request, 'proyectofinalWeb/listaVideos.html', {'playlists': playlists})
