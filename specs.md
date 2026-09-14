# Especificação Técnica — Sistema Multiagentes de Truco Mineiro (BDI + FIPA-ACL)

## 1. Escopo do jogo

- Baralho: 40 cartas (sem coringas, 8, 9, 10)
- 3 cartas por jogador por mão, melhor de 3 rodadas
- Jogo até 12 pontos
- Mesa embaralha; **não há corte nem queima de mão**
- **Manilhas fixas** (não dependem de vira/corte):
  1. 4 de Paus (Zap) — mais forte
  2. 7 de Copas
  3. A de Espadas (Espadilha)
  4. 7 de Ouros — mais fraca das manilhas
- Fora de escopo nesta fase: mão de dez, mão de ferro, família aberta/fechada, porcão

### Ordem de cartas (função de comparação)
Verificar primeiro se a carta é uma das 4 manilhas (ordem acima). Caso não seja, aplicar ordem normal:

```
3 > 2 > A > K > J > Q > 7 > 6 > 5 > 4
```
(Os outros três naipes de 7 e de 4 — que não são manilha — seguem essa ordem normal, nas posições "7" e "4" respectivamente.)

### Regras de empate por rodada
- Empate na 1ª rodada → 2ª rodada decide a mão
- Empate na 2ª ou 3ª rodada → vence quem ganhou a 1ª
- Empate em todas as rodadas → ninguém pontua

### Pontuação e escalada de aposta
- Mão sem pedido de truco: **1 ponto**
- Truco: eleva para **3**
- Seis: eleva para **6**
- Nove: eleva para **9**
- Doze: eleva para **12** (teto — não há aumento além disso)

**Máquina de estados da escalada** (implementar na mesa, não nos jogadores):
- Truco (e qualquer aumento subsequente) só pode ser pedido **a partir da 2ª rodada** da mão — proibido na 1ª rodada
- **Autoridade de pedir:** qualquer jogador da mesa, de qualquer time, pode enviar `PROPOSE`, independente de estar com a vez de jogar carta naquele instante
- **Autoridade de responder:** é sempre o **próximo jogador na ordem de turno da mesa** após quem pediu — não o parceiro de quem pediu, e não necessariamente quem jogaria carta em seguida. Como a ordem de assento numa dupla alterna entre times, esse jogador normalmente pertence ao time adversário de quem pediu
- Antes de responder, esse jogador pode consultar o parceiro reaproveitando o canal de sinalização da seção 5 (mesma chance de vazamento para o adversário)
- Respostas possíveis: `ACCEPT` (jogo continua no novo valor), `REJECT` (mão encerra, quem pediu por último ganha o valor anterior ao seu próprio pedido — não o valor pedido), ou contra-pedido do próximo nível (mesma regra de autoridade de resposta se aplica ao novo pedido, recursivamente)
- Não é possível pular níveis (ex: de truco direto para nove)

**Pontos concedidos em caso de `REJECT`, por nível pedido** (explícito para evitar erro de implementação — o valor concedido é sempre o nível anterior, nunca o nível pedido):
| Pedido feito | Se rejeitado, quem pediu ganha |
|---|---|
| Truco (pedido de 1 → 3) | 1 ponto |
| Seis (pedido de 3 → 6) | 3 pontos |
| Nove (pedido de 6 → 9) | 6 pontos |
| Doze (pedido de 9 → 12) | 9 pontos |

---

## 2. Agente de Mesa (árbitro/ambiente)

**Não é um agente BDI** — é um agente reativo/determinístico (Camada 1, reativo puro). Não possui crenças, desejos ou intenções; apenas aplica regras fixas em resposta a mensagens.

Responsabilidades:
1. Embaralhar e distribuir 3 cartas por jogador no início de cada mão
2. Validar jogadas: é a vez do jogador? A carta está na mão dele?
3. Determinar vencedor de cada rodada (via função de comparação da seção 1)
4. Aplicar regras de empate e determinar vencedor da mão
5. Gerenciar a máquina de estados de escalada de aposta (quem pode agir, quais valores são legais)
6. Atualizar e anunciar placar; verificar condição de vitória (12 pontos)
7. É o único agente com acesso ao estado completo do jogo (as duas mãos). Jogadores só recebem informação via mensagens `INFORM` explícitas — isso garante visão parcial estrutural, não dependente de disciplina de código.

---

## 3. Arquitetura do Agente Jogador (BDI)

### Beliefs (crenças)
**Factuais** (atualizadas por observação direta ou mensagem da mesa):
- Cartas na própria mão
- Histórico de cartas jogadas na mesa (próprias e do oponente)
- Placar atual
- Estado da máquina de escalada (valor atual da mão, quem pode agir)

**Psicológicas** (modelo do oponente):
- Crença de blefe por heurística fixa de personalidade (ver seção 4) — *não* é aprendida/atualizada estatisticamente nesta fase; é uma função determinística do traço de personalidade do oponente observado combinado com o estado atual da mão

### Desires (desejos)
- Vencer a rodada corrente
- Atingir 12 pontos primeiro
- Induzir o oponente a rejeitar (fugir) quando a própria mão é fraca

*Nota: "preservar cartas fortes" não é um desejo — é uma tática condicional que só se aplica em certos contextos (ver heurística de jogo de carta abaixo). Jogar a carta mais forte primeiro ("descascar") é igualmente válido e por vezes preferível.*

### Heurística de jogo de carta por rodada
- **Rodada 1, na liderança:** decisão entre descascar (jogar a carta mais forte — geralmente ativa o plano de Blefe Agressivo) ou esconder (jogar a mais fraca, testando a resposta do oponente — ativa o plano de Esconder o Jogo). Personalidade pesa fortemente aqui: Cangaceiro tende a descascar, Mão de Alface tende a esconder, Calculista compara a probabilidade de vencer a mão em cada linha de jogo.
- **Rodada 1, respondendo:** jogar a carta mais fraca que ainda vence a rodada, se existir; caso contrário, descartar a carta mais fraca.
- **Rodada 2:** depende do resultado da rodada 1 e de quantas cartas fortes o oponente já revelou. Se perdeu a 1ª, a pressão para jogar forte aumenta (perder a 2ª também encerra a mão).
- **Rodada 3:** geralmente sem decisão real — resta uma carta.

### Intentions (intenções/planos)
- Plano de Blefe Agressivo
- Plano de Esconder o Jogo (truco lento)
- Plano de Sobrevivência (fugir/rejeitar)
- Reconsideração: orientada a evento (nova informação relevante: carta jogada, pedido de aposta recebido, mensagem de sinal do parceiro), não recalculada a cada tick sem motivo

---

## 4. Personalidades (a definir em detalhe posterior)

Três perfis com pesos/limiares distintos controlando a heurística de crença de blefe e a decisão de aceitar/aumentar aposta:
1. **Mão de Alface** (conservador) — só aumenta aposta com manilha(s) certas
2. **Cangaceiro** (blefador/agressivo) — tende a pedir truco cedo, mesmo com mão fraca
3. **Calculista** (racional) — decide por probabilidade matemática da mão, ignora sinais psicológicos

*Pendente: valores numéricos exatos de threshold para cada traço.*

---

## 5. Comunicação (FIPA-ACL)

| Ato de fala | Significado no jogo |
|---|---|
| `PROPOSE(action: pedir-truco, valor: 3)` | Gritar "Truco!" |
| `PROPOSE(action: pedir-seis, valor: 6)` | Contra-pedido "Seis!" |
| (mesmo padrão para nove/doze) | |
| `ACCEPT-PROPOSAL` | "Caiu!" |
| `REJECT-PROPOSAL` | "Fugiu/Correu" |
| `INFORM(content: carta-jogada(X))` | Colocar carta X na mesa |
| `INFORM(receiver: parceiro, content: sinal(X))` | Sinal entre parceiros (modo dupla) |

### Canal de sinalização entre parceiros
Modelado como ação **parcialmente observável**, não como mensagem privada infalível: há uma chance configurável de o agente adversário também perceber o sinal e atualizar sua própria crença psicológica com base nele.
*Pendente: valor exato dessa probabilidade, e se o modo dupla entra no MVP ou fica para depois do 1x1 funcional.*

### Conteúdo e uso do sinal
- **Conteúdo:** categoria de força da própria mão (forte / média / fraca), calculada uma vez no início da mão a partir das cartas recebidas. Enviada ao parceiro via `INFORM` logo após ver a mão, e reenviável sob demanda quando o parceiro precisa decidir uma resposta de aposta (ver máquina de escalada acima).
- **Natureza da crença resultante:** diferente da crença de blefe sobre o oponente (que é probabilística/cética, via heurística de personalidade). A crença sobre a força do parceiro é tratada como informação confiável — mesma estrutura de dados de crença, fonte de atualização diferente.
- **Efeito na decisão de aposta:** aceitar/rejeitar/aumentar passa a considerar força combinada do time (própria mão + crença sobre a mão do parceiro), não só a própria mão isoladamente.
- **Efeito na heurística de jogo de carta (seção 3):** parceiro sinalizado como "forte" favorece jogo conservador (esconder) do jogador atual, contando que o parceiro resolve depois; parceiro "fraco" aumenta a pressão para descascar cedo.
- **Efeito no modelo do oponente quando o sinal vaza:** a atualização de crença de blefe do adversário deve se aplicar à dupla como um todo, não só a quem enviou o sinal — um vazamento de "fraca" deveria reduzir a crença de blefe do adversário em relação a um truco pedido por qualquer um dos dois parceiros logo em seguida.

---

## 6. Pendências abertas

- [ ] Valores de threshold de cada personalidade
- [ ] Probabilidade de vazamento do sinal entre parceiros
- [ ] Decidir se modo dupla entra no MVP ou é extensão pós-1x1
- [ ] Métrica(s)/pergunta de pesquisa para a seção de resultados do relatório final (candidatos discutidos: taxa de vitória entre personalidades, calibração da crença de blefe vs. blefe real do oponente)
