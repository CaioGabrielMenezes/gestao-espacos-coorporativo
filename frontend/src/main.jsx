import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { ProvedorPerfil } from './perfil'
import './estilos.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <ProvedorPerfil>
        <App />
      </ProvedorPerfil>
    </BrowserRouter>
  </StrictMode>
)
