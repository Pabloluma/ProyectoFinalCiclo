from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from googleapiclient.discovery import build
from .models import lista
from pytubefix import YouTube
import os
from pathlib import Path

YOUTUBE_API_KEY = 'AIzaSyDkdiJSJR8jnJSbvsIV3FSAClVxXPQ66vM'


def get_downloads_folder():
    try:
        downloads_path = Path.home() / "Downloads"
        if downloads_path.is_dir():
            return downloads_path
    except Exception:
        pass

    if os.name == 'nt':
        try:
            user_profile = os.environ.get('USERPROFILE')
            if user_profile:
                downloads_path = Path(user_profile) / "Downloads"
                if downloads_path.is_dir():
                    return downloads_path
        except Exception:
            pass
    print(
        "Advertencia: No se pudo determinar la carpeta de 'Descargas' del usuario. El archivo se guardará en el directorio de trabajo actual.")
    return Path.cwd()


def descargar_videos(video_url):
    try:
        target_folder = get_downloads_folder()
        target_folder.mkdir(parents=True, exist_ok=True)
        yt = YouTube(video_url)
        ys = yt.streams.get_highest_resolution()
        video_title = yt.title
        print(f"Descargando '{video_title}' en: {target_folder}")
        ys.download(output_path=str(target_folder))
        print("¡Descarga completada con éxito!")
        return JsonResponse({'status': 'success', 'message': f'"{video_title}" descargado con éxito.'})
    except Exception as e:
        print(f"¡Ha ocurrido un error durante la descarga! Error: {e}")
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

@login_required
def añadirLista(request):
    if request.method != "POST":
        return render(request, "error/405.html", status=405)
    else:
        url = request.POST.get('url_playlist')
        id_lista = url.split("=")
        hayvideos = obtener_videos(id_lista[1])
        if hayvideos:
            lista.objects.create(nombre=id_lista[1])

        return redirect('administracion')

def cargarVideos(request, playlist_id):
    if request.user.is_anonymous:
        return render(request, "error/404.html", status=404)
    else:
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
    if request.user.is_anonymous:
        return render(request, "error/404.html", status=404)
    else:
        playlist_objs = lista.objects.all()
        playlists = []
        for obj in playlist_objs:
            datos = obtener_todasLista(obj.nombre)
            playlists.append(datos)

        return render(request, 'proyectofinalWeb/listaVideos.html', {'playlists': playlists})
