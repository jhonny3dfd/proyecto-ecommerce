import { useState } from 'react';
import useCookieConsent from '../hooks/useCookieConsent';
import './VideoYouTube.css';

// Ícono de play en SVG: el carácter ▶ se ve como emoji en iPhone y Android
export function IconoPlay({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false">
      <path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z" fill="currentColor" />
    </svg>
  );
}

// RF-04.4: video de YouTube bajo demanda con botón accesible. Lo usan el blog (SCRUM-195) y la ficha del producto
// (pedido de Alan). La miniatura del video es una petición a YouTube (Google): solo se pide si el visitante aceptó
// las cookies de marketing, como Meta Pixel. Sin esa aceptación (o sin decidir) no se conecta a YouTube hasta el
// clic: se muestra la portada que se le pase o un fondo neutro. Al hacer clic se monta el reproductor desde
// youtube-nocookie.com. className ubica el video en cada página (márgenes y proporción)
export default function VideoYouTube({ youtubeId, titulo, portada, className = '' }) {
  const [reproduciendo, setReproduciendo] = useState(false);
  const { preferences } = useCookieConsent();

  if (!youtubeId) return null;
  // hqdefault existe para todo video; sus franjas de 4:3 quedan fuera del recuadro (object-fit: cover)
  const miniatura = preferences.marketing ? `https://i.ytimg.com/vi/${youtubeId}/hqdefault.jpg` : portada;

  return (
    <div className={`video-youtube ${className}`.trim()}>
      {reproduciendo ? (
        <iframe
          className="video-youtube-iframe"
          src={`https://www.youtube-nocookie.com/embed/${youtubeId}?autoplay=1`}
          title={`Reproductor de video: ${titulo}`}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
      ) : (
        <div className="video-youtube-facade">
          {miniatura ? (
            <img
              src={miniatura}
              alt=""
              className="video-youtube-miniatura"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="video-youtube-miniatura video-youtube-miniatura--neutra" aria-hidden="true" />
          )}
          <button
            type="button"
            className="video-youtube-reproducir"
            onClick={() => setReproduciendo(true)}
            aria-label={`Reproducir video: ${titulo}`}
          >
            <span className="video-youtube-icono-play" aria-hidden="true"><IconoPlay /></span>
            <span className="video-youtube-boton-texto">Reproducir video: {titulo}</span>
          </button>
        </div>
      )}
    </div>
  );
}
