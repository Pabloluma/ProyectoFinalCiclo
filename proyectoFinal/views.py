from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import render, redirect

# Create your views here.
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from django.contrib.auth import get_user_model

from .models import Rutas


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
    botonEnv = request.POST.get("enviar")
    if botonEnv == "reg":
        email = request.POST.get("email")
        usuario = request.POST.get("usuario")
        password_verif = request.POST.get("reppassword")
        password = request.POST.get("password")
        try:
            if password == password_verif:
                usuario = User.objects.create_user(usuario, email, password)
                usuario.save()
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
            # Generamos el enlace para el restablecimiento
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


@login_required(login_url='index')
def administracion(request):
    if request.user.is_authenticated and request.user.is_staff:
        usuario = get_user_model()
        listaUsuarios = usuario.objects.all()
        return render(request, 'proyectofinalWeb/administracion.html', {"usuarios": listaUsuarios})
    else:
        return redirect('index')


def inicio(request):
    if request.user.is_authenticated:
        if request.method == 'GET':
            listaRutas = Rutas.objects.filter(publico=True)
            return render(request, 'proyectofinalWeb/inicioRutasTodos.html', {"rutas": listaRutas})
    else:
        return redirect('index')


def accesoAnonimo(request):
    if request.user.is_anonymous:
        if request.method == 'GET':
            listaRutas = Rutas.objects.filter(publico=True)
            return render(request, 'proyectofinalWeb/vistaUsuarioAnonimo.html', {"rutas": listaRutas})
    else:
        return redirect('index')
