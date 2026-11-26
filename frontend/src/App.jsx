import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { GoogleOAuthProvider } from '@react-oauth/google';
import Login from './components/auth/Login';
import Register from './components/auth/Register';
import Checkout from './components/Checkout';
import ProtectedRoute from './components/ProtectedRoute';
import { EsqueletoPanel } from './components/carga/EsqueletosPanel';
import VariantSelector from './components/VariantSelector';
import Catalogo from './pages/Catalogo';
import LandingPage from './pages/LandingPage';
import Admin from './pages/Admin';
import { aplicarPaleta } from './constants/palettes';
import { aplicarTipografia, CLAVE_TIPOGRAFIA } from './constants/tipografias';
import DetalleProducto from './pages/DetalleProducto';
import SeguimientoEnvio from './pages/SeguimientoEnvio';
import HistorialPedidos from './pages/HistorialPedidos'; // NUEVO: Importamos el componente de historial
import MisDirecciones from './components/MisDirecciones'; // Ajusta la ruta a donde guardaste el archivo
import PagoExitoso from './components/PagoExitoso';
import PagoCancelado from './components/PagoCancelado'; // Ajusta la ruta a donde guardaste el archivo
import PedidoRecibido from './components/PedidoRecibido';
import Footer from './components/footer';
import PaginaLegal from './pages/PaginaLegal';
import Cotizacion from './pages/Cotizacion';
import Resena from './pages/Resena';
import Blog from './pages/Blog';
import PublicacionBlog from './pages/PublicacionBlog';
import SobreMi from './pages/SobreMi';
import TrackingScripts from './components/TrackingScripts';
import CookieBanner from './components/CookieBanner';
import useCookieConsent from './hooks/useCookieConsent';
import AccesibilidadNavegacion from './components/AccesibilidadNavegacion';
import useConfiguracionTienda from './hooks/useConfiguracionTienda';
import AuthLayout from './components/auth/AuthLayout';
import RecuperarContrasena from './pages/RecuperarContrasena';
import RestablecerContrasena from './pages/RestablecerContrasena';
import CambiarContrasena from './pages/CambiarContrasena';
import Suscripcion from './pages/Suscripcion';
import SuscribirsePlan from './pages/SuscribirsePlan';
import MisSuscripciones from './pages/MisSuscripciones';
import PagarEntrega from './pages/PagarEntrega';
import MiCumpleanos from './pages/MiCumpleanos';

const applyPaletteToRoot = aplicarPaleta;

// Componente para manejar la vista de autenticación (Login / Registro con Google SSO)
function AuthPage({ googleHabilitado }) {
  const [showLogin, setShowLogin] = useState(true);
  // Aviso para el login: lo deja el registro ("Tu cuenta quedó creada...", con el correo ya escrito) o la página
  // de nueva contraseña al navegar aquí ("Tu contraseña se cambió...")
  const { state } = useLocation();
  const [avisoLogin, setAvisoLogin] = useState(state?.aviso || null);

  return (
    <AuthLayout>
      {showLogin ? (
        <Login
          onSwitchToRegister={() => { setAvisoLogin(null); setShowLogin(false); }}
          googleHabilitado={googleHabilitado}
          aviso={avisoLogin}
        />
      ) : (
        <Register onSwitchToLogin={(aviso = null) => { setAvisoLogin(aviso); setShowLogin(true); }} />
      )}
    </AuthLayout>
  );
}

function App() {
  const {
    consent, preferences, isBannerOpen, storageError,
    acceptCookies, rejectCookies, savePreferences, openPreferences, closePreferences,
  } = useCookieConsent();
  // RN-04: lo informa el backend (GOOGLE_CLIENT_ID del .env); vacío = la tienda no ofrece Google
  const configuracion = useConfiguracionTienda();
  const googleClientId = configuracion?.google_client_id || '';
  // Borrador del nombre y los logos mientras el admin edita la landing (el footer está fuera de la página)
  const [marcaTemporal, setMarcaTemporal] = useState(null);
  useEffect(() => {
    if (configuracion?.tema_seleccionado !== undefined) {
      const serverId = Number(configuracion.tema_seleccionado);
      localStorage.setItem('ecommerce_palette', serverId.toString());
      applyPaletteToRoot(serverId);
    }
    if (configuracion?.tipografia_seleccionada !== undefined) {
      localStorage.setItem(CLAVE_TIPOGRAFIA, String(configuracion.tipografia_seleccionada));
      aplicarTipografia(configuracion.tipografia_seleccionada);
    }
  }, [configuracion]);
  useEffect(() => {
    // 1. Carga inicial instantánea desde localStorage
    const saved = localStorage.getItem('ecommerce_palette');
    const initialId = saved ? Number(saved) : 1;
    applyPaletteToRoot(initialId);

    // 3. Listener para cambios en la misma pestaña (CustomEvent)
    const handleCustomEvent = (e) => {
      const id = e?.detail?.temaId || Number(localStorage.getItem('ecommerce_palette')) || 1;
      applyPaletteToRoot(id);
    };

    // 4. Listener para cambios entre pestañas separadas (StorageEvent nativo)
    const handleStorageEvent = (e) => {
      if (e.key === 'ecommerce_palette' && e.newValue) {
        applyPaletteToRoot(e.newValue);
      }
    };

    window.addEventListener('themeChanged', handleCustomEvent);
    window.addEventListener('storage', handleStorageEvent);

    return () => {
      window.removeEventListener('themeChanged', handleCustomEvent);
      window.removeEventListener('storage', handleStorageEvent);
    };
  }, []);

  return (
    <BrowserRouter>
      <AccesibilidadNavegacion />
      <TrackingScripts
        googleAnalyticsId={configuracion?.google_analytics_id || ''}
        metaPixelId={configuracion?.meta_pixel_id || ''}
        analitica={preferences.analitica}
        marketing={preferences.marketing}
      />
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <div style={{ flex: 1 }}>
          <Routes>
            {/* Vistas públicas */}
            <Route path="/" element={<LandingPage onMarcaTemporal={setMarcaTemporal} />} />
            <Route path="/checkout" element={<Checkout />} />
            <Route path="/seguimiento" element={<SeguimientoEnvio />} />
            {/* Encargos, personalizados y compras en cantidad (si el admin activó el formulario) */}
            <Route path="/cotizar" element={<Cotizacion />} />
            {/* Enlace firmado del correo de entrega: /resena?t=... */}
            <Route path="/resena" element={<Resena />} />
            {/* Blog o portafolio (si el admin lo activó; si no, las páginas avisan que no está disponible) */}
            <Route path="/blog" element={<Blog />} />
            <Route path="/blog/:slug" element={<PublicacionBlog />} />
            {/* Suscripciones (si el admin las activó; si no, la página avisa que no están disponibles). Las de la cuenta
                piden iniciar sesión y vuelven a la misma página, para que sirva el enlace del correo */}
            <Route path="/suscripcion" element={<Suscripcion />} />
            <Route path="/suscripcion/:planId" element={<SuscribirsePlan />} />
            <Route path="/mis-suscripciones" element={<MisSuscripciones />} />
            <Route path="/mis-suscripciones/pagar/:ordenId" element={<PagarEntrega />} />
            {/* Página independiente Sobre mí */}
            <Route path="/sobre-mi" element={<SobreMi />} />
            <Route path="/variantes" element={<main id="contenido" tabIndex={-1} className="contenedor"><h1>Selección de variantes</h1><VariantSelector /></main>} />
            <Route path="/catalogo" element={<Catalogo />} />
            <Route path="/catalogo/producto/:id" element={<DetalleProducto />} />
            <Route path="/mis-direcciones" element={<MisDirecciones />} />
            <Route path="/pago-exitoso" element={<PagoExitoso />} />
            <Route path="/pedido-recibido" element={<PedidoRecibido />} />
            <Route path="/pago-cancelado" element={<PagoCancelado />} />
            <Route path="/pago-rechazado" element={<PagoCancelado />} />
            {/* Pantalla de login y registro */}
            {/* El script de Google se carga solo aquí y solo si la tienda ofrece Google (RN-04) */}
            <Route path="/login" element={googleClientId ? (
              <GoogleOAuthProvider clientId={googleClientId}>
                <AuthPage googleHabilitado />
              </GoogleOAuthProvider>
            ) : <AuthPage googleHabilitado={false} />} />
            {/* Contraseña olvidada: pedir el enlace por correo y elegir la nueva con ese enlace */}
            <Route path="/recuperar-contrasena" element={<RecuperarContrasena />} />
            <Route path="/restablecer-contrasena" element={<RestablecerContrasena />} />

            {/* Vista pública para desplegar páginas legales individuales (RF-03.5) */}
            <Route path="/legal/:tipo" element={<PaginaLegal />} />

            {/* NUEVO: Ruta protegida genérica (solo requiere estar logueado como cliente) */}
            <Route element={<ProtectedRoute />}>
              <Route path="/mis-pedidos" element={<HistorialPedidos />} />
              <Route path="/cambiar-contrasena" element={<CambiarContrasena />} />
              <Route path="/mi-cumpleanos" element={<MiCumpleanos />} />
            </Route>

            {/* Ruta protegida para usuarios con rol ADMIN */}
            <Route element={<ProtectedRoute allowedRoles={['ADMIN']} esqueleto={<EsqueletoPanel />} />}>
              <Route path="/admin" element={<Admin />} />
            </Route>
          </Routes>
        </div>
        
        {/* Footer inyectado dinámicamente en toda la aplicación */}
        <Footer onOpenCookiePreferences={openPreferences} marcaTemporal={marcaTemporal} />
        <CookieBanner
          consent={consent}
          preferences={preferences}
          isOpen={isBannerOpen}
          storageError={storageError}
          onAccept={acceptCookies}
          onReject={rejectCookies}
          onSave={savePreferences}
          onClose={closePreferences}
        />
      </div>
    </BrowserRouter>
  );
}

export default App;
