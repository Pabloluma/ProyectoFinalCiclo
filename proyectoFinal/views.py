import datetime
import json
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import render, redirect
import humanize
from django.utils import timezone

# Create your views here.
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt

from .models import Rutas, caracteristicas


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

                    carac = caracteristicas(tipo_bici=1, estado=0, suelo=1, usuario=usuario_reg)
                    carac.save()
            except Exception as e:
                # Hay que poner en el html que ha dado error
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
                # Enviar el correo para el restablecimiento de la contraseña
                token = default_token_generator.make_token(user)

                uid = urlsafe_base64_encode(force_bytes(user.pk))
                # Genera el enlace para restablecer la contraseña
                reset_link = request.build_absolute_uri(
                    reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
                )

                # Crear el mensaje que se enviará al usuario
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


@login_required(login_url='index')
def administracion(request):
    if request.user.is_authenticated and request.user.is_staff:
        usuario = get_user_model()
        listaUsuarios = usuario.objects.all()
        listaRutas = Rutas.objects.all()
        return render(request, 'proyectofinalWeb/administracion.html',
                      {"usuarios": listaUsuarios, "todasRutas": listaRutas})
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


def perfil(request):
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


# Hay que depurarlo salta un error en el javascript, revisar javascript y esta función
@csrf_exempt
def actualizar_usuario(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nuevo_tipo_bici = data.get('nuevo_tipo_bici')
            ruta_json = os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static\\ficheros\diccionarios.json')
            with open(ruta_json, 'r') as f:
                datos_json = json.load(f)
            dic_bici = datos_json.get("dic_bici")
            if dic_bici and isinstance(dic_bici, dict):
                for clave, valor in dic_bici.items():
                    if valor == nuevo_tipo_bici:
                        return clave
            return None
        except json.JSONDecodeError:
            print("Error: El JSON proporcionado no es válido.")
            return None
