import { useEffect, useId, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { isAdminRoute } from '../hooks/useCookieConsent';
import './CookieBanner.css';

// RF-04.4: cada categoría se acepta por separado; sin marcarla, su proveedor no se carga
const CATEGORIAS = [
  { id: 'analitica', nombre: 'Análisis', detalle: 'Google Analytics: cuántas personas visitan la tienda y qué páginas ven.' },
  { id: 'marketing', nombre: 'Publicidad', detalle: 'Meta Pixel: mide los anuncios de la tienda en Facebook e Instagram.' },
];
const NINGUNA = { analitica: false, marketing: false };

export default function CookieBanner({
  consent, preferences = NINGUNA, isOpen, storageError, onAccept, onReject, onSave, onClose,
}) {
  const { pathname } = useLocation();
  const bannerRef = useRef(null);
  const id = useId();
  const visible = isOpen && !isAdminRoute(pathname);
  // "Configurar": las casillas parten con la elección vigente (sin decidir, desmarcadas)
  const [borrador, setBorrador] = useState(null);
  const algunaAceptada = Object.values(preferences).some(Boolean);

  useEffect(() => {
    if (!visible) return;
    const previousFocus = document.activeElement;
    const banner = bannerRef.current;
    banner?.focus({ preventScroll: true });

    return () => {
      if (
        previousFocus?.isConnected &&
        (banner?.contains(document.activeElement) || document.activeElement === document.body)
      ) {
        previousFocus.focus({ preventScroll: true });
      }
    };
  }, [visible]);

  if (!visible) return null;

  const configurar = () => setBorrador({ ...NINGUNA, ...preferences });
  const guardar = () => {
    onSave(borrador);
    setBorrador(null);
  };

  const closeOnEscape = (event) => {
    if (event.key === 'Escape' && consent !== 'pending') {
      event.preventDefault();
      onClose();
    }
  };

  return (
    <section
      ref={bannerRef}
      className="cookie-banner"
      role="region"
      aria-labelledby="cookie-banner-title"
      aria-describedby="cookie-banner-description"
      tabIndex={-1}
      onKeyDown={closeOnEscape}
    >
      <div className="cookie-banner__content">
        <div className="cookie-banner__information">
          <h2 id="cookie-banner-title" className="cookie-banner__title">Tus preferencias de cookies</h2>
          <p id="cookie-banner-description" className="cookie-banner__text">
            Usamos cookies de análisis (Google Analytics) y de publicidad (Meta Pixel) solo con tu autorización.
            Puedes aceptarlas, rechazarlas o elegir cuáles, y cambiar tu elección en cualquier momento desde el pie
            de página. Te volveremos a preguntar en 12 meses.{' '}
            <Link className="cookie-banner__link" to="/legal/privacidad">Política de Privacidad</Link>.
          </p>
          {borrador && (
            <fieldset className="cookie-banner__categorias">
              <legend className="visualmente-oculto">Elige qué cookies aceptas</legend>
              {CATEGORIAS.map(({ id: categoria, nombre, detalle }) => (
                <label key={categoria} className="cookie-banner__categoria">
                  <input type="checkbox" checked={borrador[categoria]} aria-describedby={`${id}-${categoria}`}
                    onChange={(e) => setBorrador({ ...borrador, [categoria]: e.target.checked })} />
                  <span>
                    <strong>{nombre}</strong>
                    <span id={`${id}-${categoria}`} className="cookie-banner__detalle">{detalle}</span>
                  </span>
                </label>
              ))}
            </fieldset>
          )}
          {consent !== 'pending' && algunaAceptada && (
            <p className="cookie-banner__notice">
              Si rechazas algo que ya aceptaste, esta página se recargará y se reiniciarán los formularios abiertos.
            </p>
          )}
          {storageError && <p className="cookie-banner__error" role="alert">{storageError}</p>}
        </div>
        <div className="cookie-banner__actions">
          <button type="button" className="cookie-banner__button" onClick={onAccept}>Aceptar</button>
          <button type="button" className="cookie-banner__button" onClick={onReject}>Rechazar</button>
          {borrador ? (
            <button type="button" className="cookie-banner__button" onClick={guardar}>Guardar mis preferencias</button>
          ) : (
            <button type="button" className="cookie-banner__close" onClick={configurar}>Configurar</button>
          )}
          {consent !== 'pending' && (
            <button type="button" className="cookie-banner__close" onClick={onClose}>Cerrar preferencias</button>
          )}
        </div>
      </div>
    </section>
  );
}
