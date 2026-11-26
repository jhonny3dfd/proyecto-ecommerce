"""Genera el catálogo determinista y rechaza sobrescribir datos QA existentes."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from bson import ObjectId
from django.conf import settings
from django.contrib.auth import get_user_model
from mongoengine.connection import get_db
from PIL import Image
from qa_env import ADMIN_VARIABLES, require_env

from ecommerce.domain.medios_pago import CodigoMedioPago, MedioPagoConfigurado
from ecommerce.infrastructure.catalogo.documents import Producto, Variante
from ecommerce.infrastructure.ventas.models import ConfiguracionGlobal, PaginaLegal
from ecommerce.infrastructure.ventas.repositorio_medios_pago import DjangoRepositorioMediosPago


def seed():
    credentials = require_env(ADMIN_VARIABLES)
    assert settings.DATABASES['default']['NAME'] == 'ecode_qa_scrum149'
    assert get_db().name == 'ecode_qa_scrum149'
    assert not Producto.objects.count(), 'El fixture requiere un catálogo QA vacío'
    assert not get_user_model().objects.exists(), 'El fixture requiere una base QA sin usuarios'
    root = settings.QA_ROOT
    (root / 'media').mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (360, 240), '#69a68e').save(root / 'media' / 'qa149.png')
    get_user_model().objects.create_superuser(
        credentials['QA149_ADMIN_EMAIL'], credentials['QA149_ADMIN_PASSWORD'], rol='ADMIN', nombre='QA',
        apellido_paterno='Catalogo', apellido_materno='Local',
    )
    ConfiguracionGlobal.objects.create(
        pk=1, nombre_tienda='Ecode QA 149', modo_autenticacion='MIXTO',
        retiro_en_local_activo=True, calle_origen='Calle ficticia', numero_origen='149',
        comuna_origen='Santiago', texto_bienvenida='Catálogo de prueba',
        google_analytics_id='', meta_pixel_id='',
    )
    for tipo in ('TERMINOS', 'PRIVACIDAD', 'REEMBOLSOS'):
        PaginaLegal.objects.create(tipo_pagina=tipo, titulo=f'{tipo} QA',
                                  contenido='<p>Texto legal ficticio.</p>' * 400,
                                  publicada=tipo != 'REEMBOLSOS')
    repo = DjangoRepositorioMediosPago()
    repo.guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSBANK, True, {'ambiente': 'INTEGRACION'}))
    repo.guardar(MedioPagoConfigurado(CodigoMedioPago.MERCADO_PAGO, True, {}))
    repo.guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSFERENCIA, False, {}))
    ids = []
    for i in range(1200):
        categoria = 'Categoria 00' if i < 300 else f'Categoria {1 + (i - 300) % 11:02}'
        variantes = []
        for j in range(1 + i % 5):
            precio = Decimal(1000 + (i % 97) * 100 + j * 50)
            variantes.append(Variante(
                sku=f'QA149-{i:04}-{j}', precio=precio,
                precio_oferta=precio / 2 if i % 5 == 0 else None, stock=10 + i % 20,
                atributos_variables={'talla': ['S', 'M', 'L', 'XL', 'XXL'][j]},
            ))
        if i == 1079:
            variantes = []
        producto = Producto(
            id=ObjectId(f'{i + 1:024x}'), nombre=f'Producto QA149 {i:04}',
            descripcion=('Descripción ficticia del producto. ' * (1 + i % 20)),
            categoria=categoria, activo=i < 1140, publicado=i < 1080 or i >= 1170,
            fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i // 2),
            atributos_globales={'color': ['Verde', 'Azul', 'Rojo'][i % 3],
                               'capacidad_gb': [64, 128, 256][i % 3],
                               'marca': f'Marca {i % 7}'},
            imagenes=['http://127.0.0.1:8000/media/qa149.png'], variantes=variantes,
        ).save()
        if i < 30:
            Producto._get_collection().update_one({'_id': producto.id}, {'$unset': {'precio_minimo_vigente': ''}})
        elif i < 60:
            Producto._get_collection().update_one({'_id': producto.id}, {'$set': {'precio_minimo_vigente': -999}})
        ids.append(str(producto.id))
    Producto.ensure_indexes()
    manifest = {'fixture': 'scrum149-v1', 'total': 1200, 'public': 1080, 'active': 1140,
                'categories': 12, 'pages': 45, 'legacy_missing': 30, 'legacy_stale': 30,
                'ids_sha256': hashlib.sha256(''.join(ids).encode()).hexdigest()}
    (root / 'fixture.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest))


seed()
