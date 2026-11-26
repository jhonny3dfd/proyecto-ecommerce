
"""Pruebas de la página independiente Sobre mí."""

from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import ConfiguracionGlobal, ProyectoDestacadoSobreMi, Publicacion


class SobreMiTests(APITestCase):
    def setUp(self):
        self.config = ConfiguracionGlobal.objects.create(
            pk=1,
            nombre_tienda='Tienda QA',
            # Los proyectos son publicaciones del blog: solo se muestran con el blog activo
            blog_activo=True,
            sobre_mi_activo=False,
            sobre_mi_nombre='Mi historia',
            sobre_mi_biografia='<p>Diseñamos productos personalizados.</p>',
            correo_contacto='contacto@example.test',
            telefono_comercial='+56912345678',
            instagram_usuario='tiendaqa',
        )
        self.admin = create_user('admin-sobre-mi@example.test', rol='ADMIN')

        self.publicada = Publicacion.objects.create(
            titulo='Proyecto terminado',
            slug='proyecto-terminado',
            resumen='Un trabajo destacado',
            contenido='<p>Descripción del proyecto.</p>',
            estado='PUBLICADA',
        )
        self.borrador = Publicacion.objects.create(
            titulo='Proyecto en preparación',
            slug='proyecto-en-preparacion',
            resumen='Todavía no se publica',
            contenido='<p>Trabajo en proceso.</p>',
            estado='BORRADOR',
        )

    def como_admin(self):
        self.client.force_authenticate(self.admin)

    def test_pagina_desactivada_responde_404(self):
        respuesta = self.client.get(reverse('sobre-mi-publico'))
        self.assertEqual(respuesta.status_code, 404)

    def test_pagina_activada_muestra_biografia_y_contactos(self):
        self.config.sobre_mi_activo = True
        self.config.save(update_fields=['sobre_mi_activo'])

        respuesta = self.client.get(reverse('sobre-mi-publico'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['nombre'], 'Mi historia')
        self.assertEqual(
            respuesta.data['biografia'],
            '<p>Diseñamos productos personalizados.</p>',
        )
        self.assertEqual(respuesta.data['contacto']['correo'], 'contacto@example.test')
        self.assertEqual(respuesta.data['contacto']['telefono'], '+56912345678')
        self.assertEqual(respuesta.data['contacto']['instagram'], 'tiendaqa')
        self.assertEqual(respuesta.data['proyectos'], [])

    def test_contactos_vacios_no_se_muestran(self):
        self.config.sobre_mi_activo = True
        self.config.telefono_comercial = ''
        self.config.instagram_usuario = ''
        self.config.save()

        respuesta = self.client.get(reverse('sobre-mi-publico'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['contacto'], {
            'correo': 'contacto@example.test',
        })

    def test_admin_selecciona_proyectos_y_borradores_no_aparecen(self):
        self.como_admin()

        respuesta = self.client.put(
            reverse('admin-sobre-mi-proyectos'),
            {'proyectos': [self.borrador.id, self.publicada.id]},
            format='json',
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(
            respuesta.data['proyectos'],
            [self.borrador.id, self.publicada.id],
        )
        self.assertEqual(
            ProyectoDestacadoSobreMi.objects.count(),
            2,
        )

        self.config.sobre_mi_activo = True
        self.config.save(update_fields=['sobre_mi_activo'])
        self.client.force_authenticate(None)

        respuesta_publica = self.client.get(reverse('sobre-mi-publico'))

        self.assertEqual(respuesta_publica.status_code, 200)
        self.assertEqual(
            [p['slug'] for p in respuesta_publica.data['proyectos']],
            ['proyecto-terminado'],
        )

    def test_con_el_blog_apagado_no_se_muestran_los_proyectos(self):
        ProyectoDestacadoSobreMi.objects.create(configuracion=self.config, publicacion=self.publicada, orden=0)
        self.config.sobre_mi_activo = True
        self.config.blog_activo = False
        self.config.save(update_fields=['sobre_mi_activo', 'blog_activo'])

        respuesta = self.client.get(reverse('sobre-mi-publico'))

        # La página sigue disponible con su biografía; la selección se conserva para cuando el blog vuelva
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['proyectos'], [])
        self.assertEqual(respuesta.data['biografia'], '<p>Diseñamos productos personalizados.</p>')
        self.assertEqual(ProyectoDestacadoSobreMi.objects.count(), 1)

    def test_admin_puede_cambiar_el_orden(self):
        segunda = Publicacion.objects.create(
            titulo='Segundo proyecto',
            slug='segundo-proyecto',
            resumen='Otro proyecto',
            contenido='<p>Otro trabajo.</p>',
            estado='PUBLICADA',
        )
        self.como_admin()

        respuesta = self.client.put(
            reverse('admin-sobre-mi-proyectos'),
            {'proyectos': [segunda.id, self.publicada.id]},
            format='json',
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        self.config.sobre_mi_activo = True
        self.config.save(update_fields=['sobre_mi_activo'])
        self.client.force_authenticate(None)

        respuesta_publica = self.client.get(reverse('sobre-mi-publico'))

        self.assertEqual(
            [p['slug'] for p in respuesta_publica.data['proyectos']],
            ['segundo-proyecto', 'proyecto-terminado'],
        )

    def test_admin_no_puede_seleccionar_ids_repetidos(self):
        self.como_admin()

        respuesta = self.client.put(
            reverse('admin-sobre-mi-proyectos'),
            {'proyectos': [self.publicada.id, self.publicada.id]},
            format='json',
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(ProyectoDestacadoSobreMi.objects.count(), 0)

    def test_admin_no_puede_seleccionar_proyectos_inexistentes(self):
        self.como_admin()

        respuesta = self.client.put(
            reverse('admin-sobre-mi-proyectos'),
            {'proyectos': [self.publicada.id, 999999]},
            format='json',
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(ProyectoDestacadoSobreMi.objects.count(), 0)

    def test_usuario_no_autenticado_no_puede_modificar_proyectos(self):
        respuesta = self.client.put(
            reverse('admin-sobre-mi-proyectos'),
            {'proyectos': [self.publicada.id]},
            format='json',
        )

        self.assertIn(respuesta.status_code, [401, 403])
        self.assertEqual(ProyectoDestacadoSobreMi.objects.count(), 0)

    def test_admin_puede_quitar_todos_los_proyectos(self):
        ProyectoDestacadoSobreMi.objects.create(
            configuracion=self.config,
            publicacion=self.publicada,
            orden=0,
        )
        self.como_admin()

        respuesta = self.client.put(
            reverse('admin-sobre-mi-proyectos'),
            {'proyectos': []},
            format='json',
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(ProyectoDestacadoSobreMi.objects.count(), 0)

    def test_estructura_publica_y_administrativa(self):
        self.config.sobre_mi_activo = True
        self.config.save(update_fields=['sobre_mi_activo'])
        respuesta = self.client.get(reverse('sobre-mi-publico'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, {
            'nombre': 'Mi historia', 'biografia': '<p>Diseñamos productos personalizados.</p>',
            'proyectos': [], 'contacto': {'telefono': '+56912345678', 'correo': 'contacto@example.test', 'instagram': 'tiendaqa'},
            'fotos': [],
        })
        self.como_admin()
        self.assertEqual(self.client.get(reverse('admin-sobre-mi-proyectos')).data, {'proyectos': []})
        ids = [self.borrador.id, self.publicada.id]
        respuesta = self.client.put(reverse('admin-sobre-mi-proyectos'), {'proyectos': ids}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, {'proyectos': ids})
        self.assertEqual(self.client.get(reverse('admin-sobre-mi-proyectos')).data, {'proyectos': ids})

    def test_mensajes_de_ids_invalidos_y_persistencia_anterior(self):
        ProyectoDestacadoSobreMi.objects.create(configuracion=self.config, publicacion=self.publicada, orden=0)
        self.como_admin()
        casos = [
            ({}, 'Debes enviar una lista de IDs.'),
            ({'proyectos': None}, 'Debes enviar una lista de IDs.'),
            ({'proyectos': '1'}, 'Debes enviar una lista de IDs.'),
            ({'proyectos': {}}, 'Debes enviar una lista de IDs.'),
            ({'proyectos': [True]}, 'Todos los IDs deben ser números enteros positivos.'),
            ({'proyectos': [1.0]}, 'Todos los IDs deben ser números enteros positivos.'),
            ({'proyectos': [0]}, 'Todos los IDs deben ser números enteros positivos.'),
            ({'proyectos': [-1]}, 'Todos los IDs deben ser números enteros positivos.'),
            ({'proyectos': ['1']}, 'Todos los IDs deben ser números enteros positivos.'),
            ({'proyectos': [{}]}, 'Todos los IDs deben ser números enteros positivos.'),
            ({'proyectos': [self.publicada.id, self.publicada.id]}, 'No puedes seleccionar una publicación más de una vez.'),
            ({'proyectos': [999999]}, 'Una o más publicaciones no existen.'),
        ]
        for datos, mensaje in casos:
            with self.subTest(datos=datos):
                respuesta = self.client.put(reverse('admin-sobre-mi-proyectos'), datos, format='json')
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.data, {'proyectos': [mensaje]})
                self.assertEqual(self.client.get(reverse('admin-sobre-mi-proyectos')).data, {'proyectos': [self.publicada.id]})

    def test_mensajes_cuando_la_pagina_o_configuracion_no_estan_disponibles(self):
        respuesta = self.client.get(reverse('sobre-mi-publico'))
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.data, {'detail': 'La página Sobre mí no está disponible.'})
        self.config.delete()
        respuesta = self.client.get(reverse('sobre-mi-publico'))
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.data, {'detail': 'La página Sobre mí no está disponible.'})
        self.como_admin()
        respuesta = self.client.get(reverse('admin-sobre-mi-proyectos'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, {'proyectos': []})
        respuesta = self.client.put(reverse('admin-sobre-mi-proyectos'), {'proyectos': []}, format='json')
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.data, {'detail': 'Configuración de la tienda no encontrada.'})

    def test_nombre_normalizado_predeterminado_y_limite_en_api(self):
        self.como_admin()
        url = reverse('configuracion-negocio')
        for entrada, esperado in [('  Mi   historia  ', 'Mi historia'), ('   ', 'Sobre mí'), ('x' * 30, 'x' * 30)]:
            with self.subTest(entrada=entrada):
                respuesta = self.client.patch(url, {'sobre_mi_nombre': entrada}, format='json')
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.data['sobre_mi_nombre'], esperado)
                self.config.refresh_from_db()
                self.assertEqual(self.config.sobre_mi_nombre, esperado)
        respuesta = self.client.patch(url, {'sobre_mi_nombre': 'x' * 31}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.data, {'sobre_mi_nombre': ['El nombre no puede superar los 30 caracteres.']})
