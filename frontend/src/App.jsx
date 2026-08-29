import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Cadastro from './paginas/cadastro/Cadastro'
import Comparacao from './paginas/Comparacao'
import Dashboard from './paginas/Dashboard'
import Mapa from './paginas/Mapa'
import Monitoramento from './paginas/Monitoramento'
import Recomendacoes from './paginas/Recomendacoes'

const ABAS = [
  { para: '/dashboard', rotulo: 'Dashboard' },
  { para: '/mapa', rotulo: 'Mapa' },
  { para: '/recomendacoes', rotulo: 'Recomendações' },
  { para: '/comparacao', rotulo: 'Antes e depois' },
  { para: '/monitoramento', rotulo: 'Monitoramento' },
  { para: '/cadastro', rotulo: 'Cadastro' },
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
          <Route path="/mapa" element={<Mapa />} />
          <Route path="/recomendacoes" element={<Recomendacoes />} />
          <Route path="/comparacao" element={<Comparacao />} />
          <Route path="/monitoramento" element={<Monitoramento />} />
          {/* O `/*` é o que permite ao Cadastro ter rotas próprias dentro. */}
          <Route path="/cadastro/*" element={<Cadastro />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  )
}
