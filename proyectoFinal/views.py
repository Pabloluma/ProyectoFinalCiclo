import io
import json
import os
from collections import Counter
from googleapiclient.discovery import build

import humanize
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
# Create your views here.
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from matplotlib import pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from . import viewsVideos
from .decorator import usuario_no_admin_requerido
from .models import Rutas, caracteristicas, lista, Comentarios


def index(request):
    if request.method == 'POST':
        logout(request)
        return render(request, 'proyectofinalWeb/indexe.html')
    if request.method == 'GET':
        if request.user.is_authenticated:
            esAdmin = request.user.is_staff
            return redirect('inicio')
        else:
            num_Usuarios = User.objects.all().count()
            num_Rutas = Rutas.objects.all().count()
            esAdmin = request.user.is_staff
            usuariosAdmin = request.user.is_anonymous
            return render(request, 'proyectofinalWeb/indexe.html', {
                'num_Rutas': num_Rutas,
                'num_Usuarios': num_Usuarios
            })


def comentarios(request):
    if request.method == 'POST':
        ruta_sep = request.headers.get('Referer').split('/')
        id_ruta= ruta_sep[-2]
        textoComentario = request.POST.get('texto_comentario')
        ruta = Rutas.objects.get(id=id_ruta)
        nuevoComentario = Comentarios.objects.create(comentario=textoComentario, id_ruta=ruta)
        nuevoComentario.save()
        return redirect('detalles_ruta', id_ruta=id_ruta)
    else:
        return render(request, 'error/404.html', status=404)


def acceso(request):
    if request.method == "POST":
        botonEnv = request.POST.get("enviar")
        if botonEnv == "reg":
            email = request.POST.get("email")
            nombre = request.POST.get("nombre")
            apellidos = request.POST.get("apellidos")
            usuario = request.POST.get("usuario")
            password_verif = request.POST.get("reppassword")
            password = request.POST.get("password")
            try:
                if password == password_verif:
                    usuario_reg = User.objects.create_user(usuario, email, password, first_name=nombre,
                                                           last_name=apellidos)
                    usuario_reg.save()

                    carac = caracteristicas.objects.create(tipo_bici=1, estado=0, suelo=1, usuario_id=usuario_reg)
                    carac.save()
                    messages.error(request, "Se ha registrado correctamente",
                                   extra_tags="registro_valido")
            except Exception as e:
                messages.error(request, "El Nombre de usuario o el correo ya estaba registrado",
                               extra_tags="registro_fallido")
                return render(request, "proyectofinalWeb/indexe.html", {"error": str(e)})
        elif botonEnv == "ini":
            password = request.POST.get('password')
            username = request.POST.get('username')
            if username != None and password != None:
                usuario = authenticate(request, username=username, password=password)
                if usuario is not None:
                    login(request, usuario)
                    messages.success(request, "Inicio de sesión exitoso.")
                    usuariosAdmin = User.objects.filter(is_staff=True)
                    for usuario in usuariosAdmin:
                        print(usuario.username, usuario.email)
                    return redirect('inicio')
        elif botonEnv == "recPass":
            emailRec = request.POST.get('emailRec')
            try:
                user = User.objects.get(email=emailRec)

                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                reset_link = request.build_absolute_uri(
                    reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
                )

                subject = "Solicitud de Restablecimiento de Contraseña"
                message = render_to_string('proyectofinalWeb/password_reset_email.html', {
                    'user': user,
                    'reset_link': reset_link,
                })

                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [emailRec])

                messages.success(request, "Te hemos enviado un enlace de restablecimiento de contraseña a tu correo.")

            except User.DoesNotExist:
                messages.error(request, "No se encontró un usuario con ese correo electrónico.")

        return redirect('index')
    else:
        return redirect("index")


def obtener_todasLista(playlist_id):
    youtube = build('youtube', 'v3', developerKey=viewsVideos.YOUTUBE_API_KEY)
    playlist_req = youtube.playlists().list(part='snippet', id=playlist_id).execute()
    item = playlist_req['items'][0]
    snippet = item['snippet']
    return {
        'id': playlist_id,
        'title': snippet['title'],
        'description': snippet.get('description', ''),
        'thumbnail': snippet['thumbnails']['high']['url'],
    }


def cargarListas_Admin():
    playlist_objs = lista.objects.all()
    playlists = []
    for obj in playlist_objs:
        datos = obtener_todasLista(obj.nombre)
        playlists.append(datos)
    return playlists


@login_required(login_url='index')
def administracion(request):
    if request.user.is_authenticated and request.user.is_staff:
        usuario = get_user_model()
        listaUsuarios = usuario.objects.all()
        listaRutas = Rutas.objects.all()
        listaPlaylist = cargarListas_Admin()
        return render(request, 'proyectofinalWeb/administracion.html',
                      {"usuarios": listaUsuarios, "todasRutas": listaRutas, "todasPlaylist": listaPlaylist})
    else:
        return redirect('index')


def diferenciaTiempo(fecha_subida):
    fecha_actual = timezone.now()
    diferencia = fecha_actual - fecha_subida
    tiempo_relativo = humanize.naturaltime(diferencia)
    return tiempo_relativo


def inicio(request):
    if request.user.is_authenticated:
        if request.method == 'GET':
            listaRutas = Rutas.objects.filter(publico=True).prefetch_related("comentarios")
            for ruta in listaRutas:
                ruta.diferencia = diferenciaTiempo(ruta.fechaSubida)
            return render(request, 'proyectofinalWeb/inicioRutasTodos.html',
                          {"rutas": listaRutas})
    else:
        return redirect('index')


def accesoAnonimo(request):
    if request.user.is_anonymous:
        if request.method == 'GET':
            listaRutas = Rutas.objects.filter(publico=True).prefetch_related("comentarios")
            for ruta in listaRutas:
                ruta.diferencia = diferenciaTiempo(ruta.fechaSubida)
            return render(request, 'proyectofinalWeb/vistaUsuarioAnonimo.html', {"rutas": listaRutas})
    else:
        return redirect('index')


# Este decorador se ha declarado en el fichero decorator.py
@usuario_no_admin_requerido
def perfil(request):
    if request.user.is_anonymous:
        return render(request, "error/404.html", status=404)
    else:
        listaRutas = Rutas.objects.filter(idUsuario_id=request.user.id)
        listaCaract = caracteristicas.objects.filter(usuario_id_id=request.user.id)
        if listaCaract:
            ruta_json = os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static\\ficheros\diccionarios.json')
            with open(ruta_json, 'r') as f:
                datos_json = json.load(f)
            valorSuelo = datos_json['dic_suelo'][str(listaCaract[0].suelo)]
            valorBici = datos_json['dic_bici'][str(listaCaract[0].tipo_bici)]
            valorEstado = datos_json['dic_estado'][str(listaCaract[0].estado)]
            return render(request, 'proyectofinalWeb/perfil.html',
                          {"rutas": listaRutas, "caract": listaCaract, "suelo": valorSuelo, "bici": valorBici,
                           "estado": valorEstado})
        else:
            return render(request, 'proyectofinalWeb/perfil.html',
                          {"rutas": listaRutas, "caract": listaCaract})


# Falta que se cambie en la base de datos, ahora solo esta para los 3 tipos, implementar resto de campos
@csrf_exempt
# Solo permite peticiones POST
# @require_POST
def actualizar_usuario(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            valorSelec = data.get('valor')
            ruta_json = os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static\\ficheros\diccionarios.json')
            with open(ruta_json, 'r') as f:
                datos_json = json.load(f)

            for clave_principal, subdiccionario in datos_json.items():
                if isinstance(subdiccionario, dict):
                    if valorSelec in subdiccionario.values():
                        clave_json = clave_principal
                        elem_subjson = datos_json.get(clave_json)

            if elem_subjson and isinstance(elem_subjson, dict):
                for clave, valor in elem_subjson.items():
                    if valor == valorSelec:
                        print(f"Clave: {clave}")
                        return JsonResponse({'success': True, 'clave': clave})
        except json.JSONDecodeError:
            error_message = "JSON no válido"
            print(f"Error: {error_message}")
            return JsonResponse({'success': False, 'error': error_message}, status=400)
        except FileNotFoundError:
            error_message = "Archivo no encontrado"
            print(f"Error: {error_message}")
            return JsonResponse({'success': False, 'error': error_message}, status=500)
        except Exception as e:
            error_message = f'Error inesperado: {e}'
            print(f"Error: {error_message}")
            return JsonResponse({'success': False, 'error': error_message}, status=500)
        else:
            return render(request, "error/405.html", status=405)


def obtenerInforme(request):
    # # Crear respuesta como PDF
    # response = HttpResponse(content_type='application/pdf')
    # response['Content-Disposition'] = 'inline; filename="informe.pdf"'
    #
    # # Crear PDF con ReportLab
    # p = canvas.Canvas(response)
    # p.setFont("Helvetica", 14)
    # p.drawString(100, 750, "Hola mundo")
    # p.showPage()
    # p.save()
    #
    # return response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="informe_rutas.pdf"'
    rutas = Rutas.objects.all()
    conteo_usuarios = Counter(ruta.idUsuario_id for ruta in rutas)
    usuarios = User.objects.all()
    # usuarios = list(conteo_usuarios.keys())
    # num_rutas = list(conteo_usuarios.values())
    usuarios_ids = [user.id for user in usuarios]
    usuarios_nombres = [user.username for user in usuarios]

    num_rutas = [conteo_usuarios.get(user_id, 0) for user_id in usuarios_ids]
    # 2. Crear gráfico con matplotlib
    # plt.figure(figsize=(8, 5))
    # plt.bar(usuarios, num_rutas, color='skyblue')
    # plt.xlabel("ID de Usuario")
    # plt.ylabel("Número de Rutas")
    # plt.title("Número de Rutas por Usuario")
    # plt.xticks(usuarios)
    # plt.tight_layout()
    plt.figure(figsize=(10, 6))
    plt.bar(usuarios_nombres, num_rutas, color='skyblue')
    plt.xlabel("Usuario")
    plt.ylabel("Número de Rutas")
    plt.title("Número de Rutas por Usuario")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png')
    plt.close()
    img_buffer.seek(0)
    image = ImageReader(img_buffer)

    # 3. Crear PDF y dibujar el gráfico

    pdf = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    pdf.setFont("Helvetica-Bold", 18)
    pdf.setTitle("Rutas por usuario")
    pdf.drawString(100, 770, "Informe de Rutas por Usuario")
    pdf.drawImage(image, 100, 430, width=400, height=300)
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(width / 2, 380, "Este gráfico muestra cuántas rutas ha hecho cada usuario.")
    pdf.showPage()
    pdf.save()
    return response


def error_404_view(request, exception):
    return render(request, 'error/404.html', status=404)


def error_405_view(request, exception):
    return render(request, 'error/405.html', status=405)


def error_500_view(request):
    return render(request, 'error/500.html', status=500)
