import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// The design system. index.css / App.css from the Vite starter are not used.
import './styles.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
