import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Equipes from './Equipes'
import Restricoes from './Restricoes'
import Salas from './Salas'
import Setores from './Setores'
import { usarPerfil } from '../../perfil'

/**
 * Casca do cadastro (specs/cadastro.md).
 *
 * Sub-navegação própria em vez de mais quatro abas no topo: cadastrar dados e
 * analisar resultados são momentos de uso diferentes, e misturá-los deixaria a
 * barra principal com oito itens.
 */

// Salas e setores são administrados pelo Coordenador Geral; equipes e
// restrições são informadas pelos Coordenadores de Setor (seção 2).
const SUB_ABAS = [
  { para: 'salas', rotulo: 'Salas', soGeral: true },
  { para: 'setores', rotulo: 'Setores', soGeral: true },
  { para: 'equipes', rotulo: 'Equipes' },
  { para: 'restricoes', rotulo: 'Restrições' },
]

export default function Cadastro() {
  const { ehGeral, perfil } = usarPerfil()
  const subAbas = SUB_ABAS.filter((aba) => ehGeral || !aba.soGeral)
  const inicial = subAbas[0].para

  return (
    <section>
      <header className="cabecalho-secao">
        <div>
          <h2>Cadastro</h2>
          <p className="subtitulo">
            Dados que alimentam o motor. Alterações valem a partir da próxima
            otimização — execuções já registradas não mudam.
            {!ehGeral && (
              <> Como coordenador de {perfil.nome}, você informa equipes e
              restrições; salas e setores são administrados pelo Coordenador
              Geral.</>
            )}
          </p>
        </div>
      </header>

      <nav className="sub-abas">
        {subAbas.map((aba) => (
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
        <Route index element={<Navigate to={inicial} replace />} />
        <Route
          path="salas"
          element={ehGeral ? <Salas /> : <Navigate to={inicial} replace />}
        />
        <Route
          path="setores"
          element={ehGeral ? <Setores /> : <Navigate to={inicial} replace />}
        />
        <Route path="equipes" element={<Equipes />} />
        <Route path="restricoes" element={<Restricoes />} />
        <Route path="*" element={<Navigate to={inicial} replace />} />
      </Routes>
    </section>
  )
}
