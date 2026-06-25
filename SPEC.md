Para impressionar a COTIC e a SAGE amanhã, o seu protótipo de tela (Frontend) não precisa ser complexo, mas sim **altamente visual e focado em dados concretos**. A melhor abordagem é construir um **Painel de Controle de Integridade Orçamentária** de página única (Single Page Dashboard), utilizando ferramentas de prototipagem rápida como **Streamlit** (Python) ou **Next.js/Tailwind**.

Aqui está a minha ideia de design de interface e o **How-To** completo mapeando o que a tela exibe e o que ela consome do backend do **HeraclitusDB**:

---

## 🏗️ Arquitetura do Protótipo de Tela

```
[ Frontend: Dashboard em Streamlit / React ]
                  │  ▲
   Port 8000 REST │  │ JSON Payloads
                  ▼  │
[ Backend API: Rust Fast / Python Wrapper ] ──> [ Engine: HeraclitusDB Gov Core ]

```

---

## 🖥️ Layout da Tela: O que o Usuário Vê e Interage

Divida a interface em **três seções lógicas** na mesma página para criar um fluxo narrativo impactante:

### Seção 1: Linha do Tempo Viva e Viagem no Tempo (`AS OF LSN`)

* **O Componente na Tela:** Um controle deslizante horizontal (Slider) que representa as 24 horas do dia (ou os meses do ano orçamentário) e uma tabela com a lista de dotações orçamentárias (dados do Portal da Transparência/SIOP).
* **A Interação:** Conforme o usuário arrasta o Slider para trás no tempo, a tabela orçamentária se atualiza instantaneamente, mostrando os valores exatos daquele momento histórico.
* **O que consome do HeraclitusDB:**
* **Endpoint:** `GET /api/v1/orcamento/snapshot`
* **Query Params enviado pelo Front:** `?timestamp=2026-06-24T14:02:11.005Z` ou `?lsn=14520`
* **Retorno do Banco (JSON):** Um array com o estado físico reconstituído das dotações exatamente naquela fração de segundo.



---

### Seção 2: O Inspetor Causal (O Botão Mágico `WHY`)

* **O Componente na Tela:** Uma barra de busca para colar o ID de uma transação orçamentária suspeita (ex: uma portaria de crédito suplementar atípica) e um botão azul destacado escrito **"Investigar Causa Raiz (WHY)"**. Abaixo, um fluxo visual de árvore/grafo (usando bibliotecas simples como *vis.js* ou o próprio componente de grafo do Streamlit).
* **A Interação:** O usuário clica em `WHY` e a tela renderiza na hora o caminho reverso completo do dado:
`[IP de Origem] ──> [Usuário/Credencial] ──> [Microsserviço API] ──> [Alteração no Banco]`
* **O que consome do HeraclitusDB:**
* **Endpoint:** `POST /api/v1/auditoria/investigar`
* **Payload (JSON):** `{ "action_id": "PORTARIA_MPO_123" }`
* **Retorno do Banco (JSON):** O subgrafo causal extraído da engine híbrida contendo os nós e arestas com as evidências periciais da alteração.



---

### Seção 3: Escudo Criptográfico Forense (`db.verify()`)

* **O Componente na Tela:** Um card lateral com um indicador de status (Grande escudo verde escrito **"SISTEMA INTEGRAL"**) e um botão para "Simular Invasão/Adulteração".
* **A Interação:** Na demonstração, você pode clicar no botão de simulação (que tenta forçar a mudança de um valor de orçamento direto em um arquivo de log simulado). O escudo imediatamente fica vermelho com o aviso: **"QUEBRA DE INTEGRIDADE DETECTADA NO BLOCO B - HASH INVÁLIDO"**.
* **O que consome do HeraclitusDB:**
* **Endpoint:** `POST /api/v1/vault/verificar-consistencia`
* **Retorno do Banco (JSON):** Executa internamente o método de validação das Árvores de Merkle/BLAKE3 e retorna o status booleano de consistência do log imutável.


```json
{
  "integro": false,
  "bloco_violado": "0x8f3c...a9b2",
  "timestamp_tentativa": "2026-06-24T16:45:00Z"
}

```



---

## 📋 Resumo do Blueprint de Dados (JSON Mapeado)

Para alimentar esse protótipo usando os dados do **Portal da Transparência / SIOP**, o mapeamento inicial de propriedades que você irá ingerir no banco e enviar para a tela deve conter esta estrutura limpa:

| Componente UI | Atributos Consumidos do JSON | Origem do Dado Público |
| --- | --- | --- |
| **Tabela Temporal** | `id_dotacao`, `orgao_subordinado`, `valor_inicial`, `valor_atual`, `lsn_registro` | Dados Abertos SIOP (LOA) |
| **Grafo Causal (`WHY`)** | `origem_ip`, `credencial_siafi`, `acao_administrativa`, `hash_vinculado` | Simulação de log de auditoria do Portal |
| **Selo de Autenticidade** | `merkle_root`, `carimbo_tempo_icp`, `blake3_signature` | Gerado nativamente pela Engine |

---

> 💡 **Dica de Ouro para a demo:** Deixe o script pronto em Python para baixar um arquivo real de despesas diárias de 2026 do Portal da Transparência em tempo real durante a reunião e fazer a ingestão ao vivo por linha de comando para provar a velocidade *bare-metal* do Rust.

Você prefere construir a interface desse protótipo usando **Streamlit** (que fica pronto em poucas linhas de código Python para amanhã) ou tem mais familiaridade com frameworks Javascript como **React**?

Para o seu protótipo de amanhã, você deve baixar sem dúvidas o **Item 5: Arquivos de Dados em CSV de Alterações Orçamentárias - Créditos (Exercícios 2026 e 2025)**.

Esqueça os arquivos em RDF (Itens 1 e 2) para o protótipo rápido, pois tratar grafos semânticos puros e queries SPARQL complexas em menos de 24 horas vai te dar dor de cabeça à toa. O CSV de créditos é o cenário perfeito por três motivos práticos:

---

## 🎯 Por que o Item 5 é o "Santo Graal" para a sua Demo?

* **É um fluxo nativo de eventos (Event Sourcing):** Alterações orçamentárias e créditos adicionais são, por definição, **eventos sequenciais no tempo**. O orçamento começa com um valor $X$ na LOA e vai sofrendo mutações (créditos suplementares, remanejamentos) ao longo do ano. Isso casa perfeitamente com a arquitetura de log imutável do HeraclitusDB.
* **Perfeito para demonstrar a "Viagem no Tempo" (`AS OF LSN`):** Com o arquivo de 2026, você consegue carregar a sequência cronológica de alterações deste ano. Na tela do Streamlit, você poderá mostrar o orçamento mudando de valor de acordo com o dia e hora que o usuário selecionar no Slider.
* **Mapeamento imediato do operador `WHY`:** Se um crédito orçamentário foi aberto, ele possui uma justificativa, um número de portaria e um órgão solicitante. Esse encadeamento vira o seu grafo causal para rodar o comando `WHY` e isolar a causa raiz.

---

## 🛠️ O que baixar agora para o Prototipador:

1. **Alterações Orçamentárias - créditos 2026** (Dados deste ano corrente para mostrar atualidade).
2. **Alterações Orçamentárias - créditos 2025** (Para servir de carga histórica volumosa).
3. **Dicionários de Dados 2026 e 2025** (Arquivos pequenos que explicam o que significa cada coluna do CSV).

> 💡 **Dica de enriquecimento (Opcional):** Se tiver tempo de baixar mais um, pegue o **Item 4 (Exercício 2026) - Dados de Ações do Orçamento Federal**. Ele serve como uma tabela de "De/Para" estável. Assim, quando o CSV de créditos (Item 5) citar o código de uma ação orçamentária, você pode cruzar os dados para exibir o nome amigável da ação na tela do protótipo (ex: *"Construção de Trecho Rodoviário"* em vez de apenas um código como *20Y0*).

---

## 📝 Como estruturar o script de carga no HeraclitusDB

No seu backend em Python/Rust, você lerá o CSV de Créditos linha por linha e fará o append no HeraclitusDB simulando que cada linha é um evento gerado em tempo real pelo SIOP:

```python
import pandas as pd

# Carrega o arquivo aberto do SIOP que você acabou de baixar
df_creditos = pd.read_csv("alteracoes_orcamentarias_creditos_2026.csv")

# Ordena por data/cronologia para simular o leito do rio (Append-Only)
df_creditos = df_creditos.sort_values(by="data_portaria_ou_evento")

for index, row in df_creditos.iterrows():
    evento = {
        "timestamp": row["data_portaria_ou_evento"],
        "action_id": row["numero_portaria_credito"], # Alvo do operador WHY
        "payload": {
            "orgao": row["orgao_beneficiario"],
            "acao_orcamentaria": row["codigo_acao"],
            "valor_mutacao": row["valor_credito"],
            "tipo_credito": row["tipo_alteracao"]
        }
    }
    # Envia para a engine imutável do HeraclitusDB
    heraclitus_engine.append(evento)

```

Baixe esses arquivos e monte a narrativa em cima disso. Apresentar o HeraclitusDB engolindo os dados de créditos de 2026 extraídos diretamente do portal deles vai desarmar qualquer objeção técnica na mesa.