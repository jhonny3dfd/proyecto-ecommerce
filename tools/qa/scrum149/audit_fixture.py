"""Comprueba que las mediciones usan el fixture determinista sin alteraciones."""
from decimal import Decimal
import json

import manage
import django
django.setup()
from mongoengine.connection import get_db
from ecommerce.infrastructure.catalogo.documents import Producto


def audit():
    assert get_db().name == 'ecode_qa_scrum149'
    docs = list(Producto._get_collection().find().sort('_id', 1))
    assert len(docs) == 1200
    for i, doc in enumerate(docs):
        assert str(doc['_id']) == f'{i + 1:024x}'
        assert doc['nombre'] == f'Producto QA149 {i:04}'
        assert doc['activo'] == (i < 1140)
        assert doc['publicado'] == (i < 1080 or i >= 1170)
        assert doc['categoria'] == ('Categoria 00' if i < 300 else f'Categoria {1 + (i - 300) % 11:02}')
        assert doc['atributos_globales'] == {'color': ['Verde', 'Azul', 'Rojo'][i % 3],
                                           'capacidad_gb': [64, 128, 256][i % 3], 'marca': f'Marca {i % 7}'}
        assert len(doc['variantes']) == (0 if i == 1079 else 1 + i % 5)
        prices = []
        for j, variant in enumerate(doc['variantes']):
            regular = Decimal(1000 + (i % 97) * 100 + j * 50)
            assert Decimal(str(variant['precio'])) == regular, (i, j, 'precio')
            offer = regular / 2 if i % 5 == 0 else None
            assert variant.get('precio_oferta') is None if offer is None else Decimal(str(variant['precio_oferta'])) == offer
            assert variant['stock'] == 10 + i % 20
            prices.append(offer if offer is not None else regular)
        if i < 30:
            assert 'precio_minimo_vigente' not in doc
        elif i < 60:
            assert doc['precio_minimo_vigente'] == -999
        else:
            actual = doc.get('precio_minimo_vigente')
            assert actual is None if not prices else Decimal(str(actual)) == min(prices)
    print(json.dumps({'fixture': 'scrum149-v1', 'documents_checked': len(docs), 'unchanged': True}))


if __name__ == '__main__':
    audit()
