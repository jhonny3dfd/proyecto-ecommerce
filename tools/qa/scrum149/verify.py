"""Verifica endpoints HTTP reales y sus documentos persistidos en QA."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

import requests
from qa_env import ADMIN_VARIABLES, require_env

import manage
import django
django.setup()
from django.conf import settings
from mongoengine.connection import get_db
from ecommerce.infrastructure.catalogo.documents import Producto

BASE = 'http://127.0.0.1:8000/api/'


def price(product):
    values = []
    for variant in product.get('variantes', []):
        regular = Decimal(str(variant['precio']))
        offer = Decimal(str(variant['precio_oferta'])) if variant.get('precio_oferta') else None
        values.append(offer if offer is not None and 0 < offer < regular else regular)
    return min(values) if values else None


def verify(output):
    credentials = require_env(ADMIN_VARIABLES)
    output.parent.mkdir(parents=True, exist_ok=True)
    assert get_db().name == 'ecode_qa_scrum149'
    assert settings.DATABASES['default']['NAME'] == 'ecode_qa_scrum149'
    checks = []
    public = requests.Session()
    admin = requests.Session()
    def check(name, condition):
        checks.append({'case': name, 'passed': bool(condition)})
        if not condition:
            raise AssertionError(f'Falló la comprobación: {name}')
    def get(path, session=public, **params):
        response = session.get(BASE + path, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    def patch(path, data):
        response = admin.patch(BASE + path, json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    def pages(**params):
        first = get('catalogo/productos/', **params)
        products = first['results']
        for page in range(2, first['total_pages'] + 1):
            data = get('catalogo/productos/', page=page, **params)
            check(f'count/page/{params}/{page}', data['count'] == first['count'] and data['current_page'] == page)
            products.extend(data['results'])
        check(f'no_duplicates/{params}', len({p['id'] for p in products}) == len(products) == first['count'])
        return products
    try:
        all_public = pages()
        check('1080_public_45_pages', len(all_public) == 1080)
        check('public_visibility', all(p['activo'] and p['publicado'] for p in all_public))
        filters = get('catalogo/filtros/')
        check('global_categories', len(filters['categorias']) == 12)
        check('global_options_equal', get('catalogo/productos/')['filtros'] == filters)
        check('category', get('catalogo/productos/', categoria='Categoria 00')['count'] == 300)
        check('numeric_attribute', get('catalogo/productos/', categoria='Categoria 00', atributo_capacidad_gb='128')['count'] == 100)
        check('text_attribute', get('catalogo/productos/', categoria='Categoria 00', atributo_color='Verde')['count'] == 100)
        check('empty_filter', get('catalogo/productos/', atributo_color='No existe')['count'] == 0)
        check('out_of_range', get('catalogo/productos/', page=999)['results'] == [])
        check('page_bounds', get('catalogo/productos/', page=-1, page_size=999)['page_size'] == 100)
        for order in ('precio-asc', 'precio-desc'):
            products = pages(orden=order)
            actual = [(price(p), p['id']) for p in products]
            def key(item):
                value, id_ = item
                return (value is not None, value or Decimal(0), id_) if order == 'precio-asc' else (value is None, -(value or Decimal(0)), id_)
            check('global_visible_price/' + order, actual == sorted(actual, key=key))
        for i in (1081, 1141, 1171):
            check(f'hidden_detail/{i}', public.get(BASE + f'catalogo/productos/{i:024x}/', timeout=30).status_code == 404)
        check('public_all_mode', len(get('catalogo/productos/', todos='true')) == 1080)
        login = admin.post(BASE + 'usuarios/token/', json={
            'email': credentials['QA149_ADMIN_EMAIL'], 'password': credentials['QA149_ADMIN_PASSWORD'],
        }, timeout=30)
        login.raise_for_status()
        admin.headers['Authorization'] = 'Bearer ' + login.json()['access']
        inventory = get('catalogo/productos/', admin, todos='true')
        check('inventory_complete', len(inventory) == 1140)
        check('form_categories', len({p['categoria'] for p in inventory}) == 12)
        id_ = f'{1:024x}'
        path = 'catalogo/productos/' + id_ + '/'
        original = Producto._get_collection().find_one({'_id': Producto.objects.get(id=id_).id})
        try:
            stages = [[{'sku': 'QA149-EDIT', 'precio': '20000', 'stock': 10}],
                      [{'sku': 'QA149-EDIT', 'precio': '20000', 'precio_oferta': '500', 'stock': 10}],
                      [{'sku': 'QA149-EDIT', 'precio': '20000', 'stock': 10}, {'sku': 'QA149-ADDED', 'precio': '100', 'stock': 10}],
                      [{'sku': 'QA149-EDIT', 'precio': '20000', 'stock': 10}]]
            for index, variants in enumerate(stages):
                updated = patch(path, {'variantes': variants})
                persisted = Producto._get_collection().find_one({'_id': original['_id']})
                check(f'persist_effective_price/{index}', Decimal(str(persisted['precio_minimo_vigente'])) == price(updated))
                for order in ('precio-asc', 'precio-desc'):
                    sorted_products = pages(orden=order, categoria='Categoria 00')
                    values = [price(p) for p in sorted_products]
                    check(f'edited_order/{index}/{order}', values == sorted(values, reverse=order == 'precio-desc'))
            patch(path, {'publicado': False})
            check('unpublish_fresh', get('catalogo/productos/')['count'] == 1079)
            patch(path, {'publicado': True, 'atributos_globales': {'solo_qa149': 'Cambio inmediato'}})
            check('filter_freshness', 'Cambio inmediato' in get('catalogo/filtros/')['atributos']['Categoria 00']['solo_qa149'])
            patch(path, {'activo': False})
            check('deactivate_fresh', get('catalogo/productos/')['count'] == 1079)
        finally:
            Producto._get_collection().replace_one({'_id': original['_id']}, original)
        config = get('configuracion/negocio/', admin)
        try:
            patch('configuracion/negocio/', {'nombre_tienda': 'Cambio QA149', 'layout_catalogo': 'LISTA'})
            check('configuration_fresh', get('configuracion/')['nombre_tienda'] == 'Cambio QA149')
        finally:
            patch('configuracion/negocio/', {'nombre_tienda': config['nombre_tienda'], 'layout_catalogo': config['layout_catalogo']})
        check('legal_visibility', len(get('ventas/paginas-legales/')) == 2)
    finally:
        output.write_text(json.dumps(checks, indent=2), encoding='utf-8')
    print(json.dumps({'passed': len(checks), 'failed': sum(not c['passed'] for c in checks)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Archivo JSON de resultados temporales')
    verify(parser.parse_args().output)
