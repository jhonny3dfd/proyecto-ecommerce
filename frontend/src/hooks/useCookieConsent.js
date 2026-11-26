import { useSyncExternalStore } from 'react';

// RF-04.4: consentimiento por categoría. 'analitica' habilita Google Analytics y 'marketing', Meta Pixel. Nada se
// carga sin una aceptación explícita: sin decidir (o con el banner ignorado) todo queda bloqueado.
export const COOKIE_CONSENT_KEY = 'ecode_cookie_consent';
export const CATEGORIAS = ['analitica', 'marketing'];
// La decisión (aceptar o rechazar) vale 12 meses; después se vuelve a preguntar
export const VIGENCIA_CONSENTIMIENTO_MS = 365 * 24 * 60 * 60 * 1000;

const NINGUNA = Object.freeze({ analitica: false, marketing: false });
const TODAS = Object.freeze({ analitica: true, marketing: true });

const listeners = new Set();
const initialSnapshot = { consent: 'pending', preferences: NINGUNA, isBannerOpen: true, storageError: '' };
let snapshot;

export function isAdminRoute(pathname) {
  let normalized = pathname.toLowerCase();
  try {
    normalized = decodeURIComponent(pathname).toLowerCase();
  } catch {
    // Una URL mal codificada no debe interrumpir el control de consentimiento.
  }
  return normalized === '/admin' || normalized.startsWith('/admin/');
}

// 'accepted' (todas), 'rejected' (ninguna), 'custom' (solo algunas) o 'pending' (sin decisión vigente)
const resumen = (preferencias) => {
  const aceptadas = CATEGORIAS.filter((categoria) => preferencias[categoria]).length;
  if (aceptadas === CATEGORIAS.length) return 'accepted';
  return aceptadas === 0 ? 'rejected' : 'custom';
};

const aceptaAlguna = (preferencias) => CATEGORIAS.some((categoria) => preferencias[categoria]);
const mismasPreferencias = (a, b) => CATEGORIAS.every((categoria) => a[categoria] === b[categoria]);
const serializar = (preferencias) => JSON.stringify({ ...preferencias, fecha: new Date().toISOString() });

// Lo guardado: { analitica, marketing, fecha }. Vencida, ilegible o de otra forma, no hay decisión (se pregunta).
// Del formato anterior (un texto): un rechazo se respeta y desde ahora corre su vigencia; una aceptación se vuelve a
// preguntar, porque se dio sin poder elegir por categoría.
function interpretar(guardado) {
  if (guardado === 'rejected') return { preferencias: NINGUNA, actualizar: true };
  if (!guardado || !guardado.startsWith('{')) return null;
  try {
    const valor = JSON.parse(guardado);
    const fecha = Date.parse(valor?.fecha);
    const valido = CATEGORIAS.every((categoria) => typeof valor[categoria] === 'boolean') && Number.isFinite(fecha);
    if (!valido || Date.now() - fecha > VIGENCIA_CONSENTIMIENTO_MS) return null;
    return { preferencias: { analitica: valor.analitica, marketing: valor.marketing }, actualizar: false };
  } catch {
    return null;
  }
}

function readStoredConsent() {
  try {
    const guardado = window.localStorage.getItem(COOKIE_CONSENT_KEY);
    const decision = interpretar(guardado);
    if (!decision) return { consent: 'pending', preferences: NINGUNA, storageError: '' };
    if (decision.actualizar) {
      window.localStorage.setItem(COOKIE_CONSENT_KEY, serializar(decision.preferencias));
    } else if (aceptaAlguna(decision.preferencias)) {
      // No habilitar una aceptación antigua si ahora no se puede guardar su retirada.
      window.localStorage.setItem(COOKIE_CONSENT_KEY, guardado);
    }
    return { consent: resumen(decision.preferencias), preferences: decision.preferencias, storageError: '' };
  } catch {
    return {
      consent: 'pending',
      preferences: NINGUNA,
      storageError: 'No pudimos acceder a tus preferencias de cookies. El seguimiento sigue bloqueado.',
    };
  }
}

function getSnapshot() {
  if (!snapshot) {
    const stored = readStoredConsent();
    snapshot = { ...stored, isBannerOpen: stored.consent === 'pending' };
  }
  return snapshot;
}

function publish(next) {
  snapshot = { ...getSnapshot(), ...next };
  listeners.forEach((listener) => listener());
}

// También se consulta desde los efectos para impedir que un render anterior reactive un proveedor después de una
// retirada síncrona del consentimiento. Sin categoría: si hay alguna aceptada.
export function isCookieConsentAccepted(categoria) {
  const { preferences } = getSnapshot();
  return categoria ? Boolean(preferences[categoria]) : aceptaAlguna(preferences);
}

export function suspendTracking(categorias = CATEGORIAS) {
  if (categorias.includes('analitica')) {
    for (const id of window.__ecodeGaInitialized || []) {
      window[`ga-disable-${id}`] = true;
    }

    // Conservar js/config, pero nunca reproducir visitas pendientes al reanudar.
    if (Array.isArray(window.dataLayer) && !window.__ecodeGaScriptLoaded) {
      const commands = window.dataLayer.filter((command) => command?.[0] !== 'event');
      window.dataLayer.splice(0, window.dataLayer.length, ...commands);
    }
  }

  if (categorias.includes('marketing') && typeof window.fbq === 'function') {
    if (!window.fbq.callMethod && Array.isArray(window.fbq.queue)) {
      const commands = window.fbq.queue.filter((command) => (
        command?.[0] !== 'consent' && !String(command?.[0]).startsWith('track')
      ));
      // Revoke debe preceder a init si la librería todavía está descargándose.
      window.fbq.queue = [['consent', 'revoke'], ...commands];
    } else {
      window.fbq('consent', 'revoke');
    }
  }
}

function removeTrackingScripts(categorias) {
  if (categorias.includes('analitica')) document.getElementById('ecode-google-analytics-script')?.remove();
  if (categorias.includes('marketing')) document.getElementById('ecode-meta-pixel-script')?.remove();
}

function inicializada(categoria) {
  return categoria === 'analitica'
    ? Boolean(window.__ecodeGaInitialized?.length)
    : Boolean(window.__ecodeMetaPixelInitialized?.length);
}

// Bloquea lo que no está aceptado y recarga si se retiró algo que ya estaba funcionando (sin recargar, la librería
// cargada podría seguir registrando)
function aplicarBloqueos(antes, despues, puedeRecargar) {
  const bloqueadas = CATEGORIAS.filter((categoria) => !despues[categoria]);
  const retiradas = bloqueadas.filter((categoria) => antes[categoria] || inicializada(categoria));
  suspendTracking(bloqueadas);
  removeTrackingScripts(bloqueadas);
  if (retiradas.length && puedeRecargar) window.location.reload();
}

function chooseConsent(preferencias) {
  const antes = getSnapshot().preferences;
  let storageError = '';

  try {
    const valor = serializar(preferencias);
    window.localStorage.setItem(COOKIE_CONSENT_KEY, valor);
    if (window.localStorage.getItem(COOKIE_CONSENT_KEY) !== valor) {
      throw new Error('La decisión de cookies no se guardó.');
    }
  } catch {
    storageError = 'No pudimos guardar tu elección. El seguimiento sigue bloqueado. Inténtalo nuevamente.';
  }

  // Sin poder guardar, nada se habilita: una aceptación queda pendiente y un rechazo vale solo en esta página
  const efectivas = storageError ? NINGUNA : preferencias;
  const consent = storageError && aceptaAlguna(preferencias) ? 'pending' : resumen(efectivas);
  publish({ consent, preferences: efectivas, isBannerOpen: Boolean(storageError), storageError });
  // Sin persistencia, recargar podría restaurar una aceptación anterior.
  aplicarBloqueos(antes, efectivas, !storageError);
}

function syncStoredConsent(event) {
  const current = getSnapshot();
  const next = readStoredConsent();

  // Una página restaurada no debe recuperar una aceptación cuya retirada falló.
  if (current.storageError && aceptaAlguna(next.preferences) && event.type !== 'storage') return;
  if (current.consent === next.consent && mismasPreferencias(current.preferences, next.preferences)
      && current.storageError === next.storageError) return;

  publish({ ...next, isBannerOpen: next.consent === 'pending' || Boolean(next.storageError) });
  aplicarBloqueos(current.preferences, next.preferences, !next.storageError);
}

function handleStorage(event) {
  if (event.key !== COOKIE_CONSENT_KEY && event.key !== null) return;
  try {
    if (event.storageArea !== window.localStorage) return;
  } catch {
    // Si el navegador retiró acceso al almacenamiento, sincronizar también bloquea el seguimiento.
  }
  syncStoredConsent(event);
}

function subscribe(listener) {
  listeners.add(listener);
  if (listeners.size === 1) {
    window.addEventListener('storage', handleStorage);
    // Al volver a la página (ej. desde el historial) también se revisa si la decisión venció
    window.addEventListener('pageshow', syncStoredConsent);
    syncStoredConsent({ type: 'subscribe' });
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      window.removeEventListener('storage', handleStorage);
      window.removeEventListener('pageshow', syncStoredConsent);
    }
  };
}

const acceptCookies = () => chooseConsent(TODAS);
const rejectCookies = () => chooseConsent(NINGUNA);
// Solo las categorías conocidas; lo que no venga marcado queda rechazado
const savePreferences = (preferencias) => chooseConsent(
  Object.fromEntries(CATEGORIAS.map((categoria) => [categoria, preferencias?.[categoria] === true])));
const openPreferences = () => publish({ isBannerOpen: true });
const closePreferences = () => {
  if (getSnapshot().consent !== 'pending') publish({ isBannerOpen: false });
};
const getServerSnapshot = () => initialSnapshot;

export default function useCookieConsent() {
  const state = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return { ...state, acceptCookies, rejectCookies, savePreferences, openPreferences, closePreferences };
}
