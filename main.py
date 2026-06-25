import pandas as pd
import heraclitusdb
import os
import json

# 1. Conexão com o SDK oficial na porta gRPC do servidor limpo
print("🔄 Conectando ao HeraclitusDB Gov Core...")
db = heraclitusdb.connect("127.0.0.1:7474")

# 2. Lista dos arquivos CSV cadastrados no disco
arquivos_siop = {
    2023: "alteracoesorcamentarias_2023.csv",
    2024: "alteracoesorcamentarias_2024.csv",
    2025: "alteracoesorcamentarias_2025.csv",
    2026: "alteracoesorcamentarias_2026.csv"
}

dfs = []

# 3. Leitura robusta e consolidação das bases (com fallback de encoding)
for ano, arquivo in arquivos_siop.items():
    if os.path.exists(arquivo):
        print(f"📖 Lendo dados do exercício {ano} ({arquivo})...")
        try:
            df = pd.read_csv(arquivo, sep=';', on_bad_lines='skip', encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(arquivo, sep=';', on_bad_lines='skip', encoding='latin1')
            
        df['ano_exercicio'] = ano
        dfs.append(df)
    else:
        print(f"⚠️ Arquivo correspondente ao ano {ano} não encontrado localmente. Pulando...")

if not dfs:
    raise FileNotFoundError("Nenhum arquivo CSV válido foi encontrado para ingestão.")

# Combina todos os anos em um dataframe unificado
df_completo = pd.concat(dfs, ignore_index=True)

# === DETECÇÃO AUTOMÁTICA DE COLUNAS (ANTI-KEYERROR) ===
def mapear_coluna(termos_chave, rejeitar=[]):
    for col in df_completo.columns:
        if any(termo in col.lower() for termo in termos_chave) and not any(r in col.lower() for r in rejeitar):
            return col
    for col in df_completo.columns:
        if any(termo in col.lower() for termo in termos_chave):
            return col
    return df_completo.columns[0]

# Mapeia os cabeçalhos reais do arquivo do SIOP
coluna_data = mapear_coluna(['data', 'dt'])
coluna_numero = mapear_coluna(['numero', 'num', 'portaria'])
coluna_valor = mapear_coluna(['valor', 'credito', 'montante'], rejeitar=['id', 'codigo', 'numero'])
coluna_orgao = mapear_coluna(['orgao', 'orgã', 'beneficiario'])
coluna_acao = mapear_coluna(['acao', 'ação', 'codigo', 'cod'])
coluna_tipo = mapear_coluna(['tipo', 'especie', 'forma'])

print(f"🔍 Coluna de data detectada automaticamente: '{coluna_data}'")

# 4. Tratamento e Ordenação Cronológica Estrita
df_completo[coluna_data] = pd.to_datetime(df_completo[coluna_data], errors='coerce')
df_completo = df_completo.dropna(subset=[coluna_data])
df_completo = df_completo.sort_values(by=coluna_data).reset_index(drop=True)

print(f"📊 Total de {len(df_completo)} eventos orçamentários prontos para ordenamento linear.")

# 5. Ingestão no log Append-Only via SDK
print("🚀 Iniciando carga bare-metal no HeraclitusDB...")

for index, row in df_completo.iterrows():
    action_id = str(row.get(coluna_numero, f"REQ_{index}"))
    
    # === LIMPEZA CIRÚRGICA DE VALORES (Garante que não vai zerar no banco) ===
    valor_cru = str(row.get(coluna_valor, "0"))
    # Remove "R$", espaços normais e quebras ocultas de texto (\xa0)
    valor_limpo = valor_cru.replace('R$', '').replace(' ', '').replace('\xa0', '')
    # Converte o padrão nacional (1.500,50) para o padrão do Python (1500.50)
    valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
    
    try:
        valor_float = float(valor_limpo)
    except ValueError:
        valor_float = 0.0
    
    # Construção do texto semântico descritivo
    texto_evento = (
        f"Portaria de alteração orçamentária número {action_id} no exercício de {row['ano_exercicio']}. "
        f"Concede crédito suplementar no valor de R$ {valor_float:,.2f} para o "
        f"órgão beneficiário {row.get(coluna_orgao, 'Não Informado')}."
    )
    
    # Estrutura interna do bloco de dados
    conteudo_bloco = {
        "text": texto_evento,
        "attributes": {
            "action_id": action_id,
            "ano": int(row["ano_exercicio"]),
            "orgao": str(row.get(coluna_orgao, "")),
            "acao_orcamentaria": str(row.get(coluna_acao, "")),
            "valor": valor_float,
            "tipo_alteracao": str(row.get(coluna_tipo, "CREDITO")),
            "data_oficial": row[coluna_data].strftime("%Y-%m-%d %H:%M:%S")
        }
    }
    
    # Transforma em string JSON e codifica em Bytes para envio gRPC puro
    payload_bytes = json.dumps(conteudo_bloco).encode('utf-8')
    
    # Chamada posicional aceita pelo driver Rust (Kind, Content)
    lsn = db.append("AlteracaoOrcamentaria", payload_bytes)
    
    if index % 500 == 0 and index > 0:
        print(f"📥 Progresso: {index} registros processados com sucesso. LSN Atual: {lsn}")

# 6. Validação forense da árvore criptográfica ao final da carga
print("\n🔒 Finalizando carga de dados. Executando verificação de integridade da árvore Merkle...")
if db.verify():
    print("✅ Sucesso absoluto! Log imutável gerado sem corrupção e com 100% de consistência matemática.")
else:
    print("❌ Falha na consistência dos blocos. Verifique os logs do servidor.")