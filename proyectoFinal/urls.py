from . import views, viewsRutas, viewsVideos
from . import viewsCalculaDureza
from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='index'),
    path('anonimo/', views.accesoAnonimo, name='anonimo'),
    path('acceso/', views.acceso, name='registroAcceso'),
    path('inicio/', views.inicio, name='inicio'),
    path('misRutas/', viewsRutas.mis_rutas, name='misRutas'),
    path('misRutas/nueva', viewsRutas.formularioNuevaRuta, name='nuevaRuta'),

    path('administracion/', views.administracion, name='administracion'),
    path('durezaRuta/', viewsCalculaDureza.calcular, name='calcularDureza'),
    path('listaVideos/', viewsVideos.mostrarLista, name='listaVideos'),

    path('listaVideos/videos', viewsVideos.cargarVideos, name='videos'),

    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),

    # Vista para la confirmación de la solicitud de restablecimiento
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),

    # Vista para el enlace de restablecimiento de contraseña
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),

    # Vista para la confirmación después de restablecer la contraseña
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
