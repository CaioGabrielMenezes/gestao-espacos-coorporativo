import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Comparacao from './paginas/Comparacao'
import Dashboard from './paginas/Dashboard'
import Monitoramento from './paginas/Monitoramento'
import Recomendacoes from './paginas/Recomendacoes'

const ABAS = [
  { para: '/dashboard', rotulo: 'Dashboard' },
  { para: '/recomendacoes', rotulo: 'Recomendações' },
  { para: '/comparacao', rotulo: 'Antes e depois' },
  { para: '/monitoramento', rotulo: 'Monitoramento' },
]

export default function App() {
  return (
    <div className="aplicacao">
      <header className="topo">
        <h1>Gestão de Espaços Corporativos</h1>
        <nav>
          {ABAS.map((aba) => (
            <NavLink
              key={aba.para}
              to={aba.para}
              className={({ isActive }) => (isActive ? 'ativo' : '')}
            >
              {aba.rotulo}
            </NavLink>
          ))}
        </nav>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/recomendacoes" element={<Recomendacoes />} />
          <Route path="/comparacao" element={<Comparacao />} />
          <Route path="/monitoramento" element={<Monitoramento />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  )
}
