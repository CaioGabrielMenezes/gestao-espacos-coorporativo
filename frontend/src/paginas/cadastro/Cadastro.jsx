import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Equipes from './Equipes'
import Restricoes from './Restricoes'
import Salas from './Salas'
import Setores from './Setores'

/**
 * Casca do cadastro (specs/cadastro.md).
 *
 * Sub-navegação própria em vez de mais quatro abas no topo: cadastrar dados e
 * analisar resultados são momentos de uso diferentes, e misturá-los deixaria a
 * barra principal com oito itens.
 */

const SUB_ABAS = [
  { para: 'salas', rotulo: 'Salas' },
  { para: 'setores', rotulo: 'Setores' },
  { para: 'equipes', rotulo: 'Equipes' },
  { para: 'restricoes', rotulo: 'Restrições' },
]

export default function Cadastro() {
  return (
    <section>
      <header className="cabecalho-secao">
        <div>
          <h2>Cadastro</h2>
          <p className="subtitulo">
            Dados que alimentam o motor. Alterações valem a partir da próxima
            otimização — execuções já registradas não mudam.
          </p>
        </div>
      </header>

      <nav className="sub-abas">
        {SUB_ABAS.map((aba) => (
          <NavLink
            key={aba.para}
            to={aba.para}
            className={({ isActive }) => (isActive ? 'ativo' : '')}
          >
            {aba.rotulo}
          </NavLink>
        ))}
      </nav>

      <Routes>
        <Route index element={<Navigate to="salas" replace />} />
        <Route path="salas" element={<Salas />} />
        <Route path="setores" element={<Setores />} />
        <Route path="equipes" element={<Equipes />} />
        <Route path="restricoes" element={<Restricoes />} />
      </Routes>
    </section>
  )
}
