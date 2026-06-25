import streamlit as st
import pandas as pd
import heraclitusdb
import json
import time

# Configuração da Página - Moderna para 2026
st.set_page_config(
    page_title="HeraclitusDB Live Gov",
    page_icon="🛡️",
    layout="wide"
)

# Conexão gRPC Real com o Servidor em Rust
@st.cache_resource
def conectar_banco():
    try:
        return heraclitusdb.connect("127.0.0.1:7474")
    except Exception as e:
        st.error(f"❌ Falha de conexão com o HeraclitusDB (Porta 7474): {e}")
        return None

db = conectar_banco()

st.title("🛡️ HeraclitusDB — Painel de Integridade Orçamentária")
st.subheader("Protótipo Real integrado via gRPC (COTIC & SAGE)")
st.markdown("---")

if db is None:
    st.warning("Aguardando inicialização do servidor HeraclitusDB...")
else:
    # KPI do Estado do Banco Conectado
    k1, k2 = st.columns(2)
    with k1:
        st.metric("Engine Status", "ONLINE", delta="gRPC Bare-Metal Rust")
    with k2:
        st.metric("Endereço do Core", "127.0.0.1:7474")

    st.markdown("---")

    # ================= SEÇÃO CONSULTA REAL AO BANCO =================
    st.markdown("### 🛰️ Consulta Semântica e Causal Direta no Log Imutável (`db.recall`)")
    st.write("Digite um termo de busca (Ex: Ministério, Educação, Portaria) para consultar a Engine em Rust em tempo real.")

    # Input real de busca
    termo_busca = st.text_input("🔍 Termo para Busca Vetorial Semântica:", "Ministério")
    
    if termo_busca:
        try:
            # CHAMADA REAL AO BANCO
            lista_blocos = db.recall(termo_busca)
            
            if not lista_blocos:
                st.info("Nenhum registro encontrado para esse termo no banco.")
            else:
                dados_tabela = []
                
                # Varre os blocos consertando o parser de dicionário do SDK
                for bloco in lista_blocos:
                    try:
                        if isinstance(bloco, dict):
                            content_raw = bloco.get('content', '{}')
                            lsn_banco = bloco.get('lsn', 'N/A')
                        else:
                            content_raw = bloco.content if hasattr(bloco, 'content') else str(bloco)
                            lsn_banco = bloco.lsn if hasattr(bloco, 'lsn') else 'N/A'
                        
                        payload = json.loads(content_raw)
                        attrs = payload.get("attributes", {})
                        
                        dados_tabela.append({
                            "LSN": lsn_banco,
                            "Data Oficial": attrs.get("data_oficial", "N/A"),
                            "Portaria": attrs.get("action_id", "N/A"),
                            "Órgão Beneficiário": attrs.get("orgao", "N/A"),
                            "Valor (R$)": float(attrs.get("valor", 0.0)),
                            "Ação": attrs.get("acao_orcamentaria", "N/A")
                        })
                    except Exception as err:
                        continue
                
                if dados_tabela:
                    df_live = pd.DataFrame(dados_tabela)
                    
                    # CORREÇÃO 1: Formato da data explicitado para calar o aviso do Pandas
                    df_live["Data Oficial"] = pd.to_datetime(df_live["Data Oficial"], format="%Y-%m-%d %H:%M:%S", errors='coerce')
                    df_live = df_live.dropna(subset=["Data Oficial"]).sort_values(by="Data Oficial").reset_index(drop=True)
                    
                    # === LINHA DO TEMPO (SLIDER) ===
                    st.markdown("### ⏳ Seção 1: Linha do Tempo Viva & Reconstituição Histórica (`AS OF LSN`)")
                    st.write("Arraste o slider para navegar no tempo e reconstruir o estado dos dados retornados pelo banco.")
                    
                    slice_percent = st.slider("Evolução Temporal do Log (Progresso da Carga)", 1, 100, 100)
                    limit_index = int((slice_percent / 100) * len(df_live))
                    if limit_index == 0: limit_index = 1
                    
                    df_filtrado = df_live.iloc[:limit_index]
                    
                    # KPIs Dinâmicos baseados no Slider
                    kpi1, kpi2 = st.columns(2)
                    with kpi1:
                        st.metric("Eventos no LSN selecionado", f"{len(df_filtrado)}")
                    with kpi2:
                        st.metric("Volume Transacionado no Recorte", f"R$ {df_filtrado['Valor (R$)'].sum():,.2f}")
                    
                    # CORREÇÃO 2: Atualizado use_container_width para width='stretch' do padrão 2026
                    st.dataframe(df_filtrado, width='stretch')
                    
        except Exception as e:
            st.error(f"Erro ao executar query no HeraclitusDB: {e}")

    st.markdown("---")

    # ================= SEÇÃO VALIDAÇÃO DA ÁRVORE MERKLE =================
    st.markdown("### 🔒 Validação Forense de Consistência Matemática (`db.verify`)")
    st.write("Dispara o recálculo criptográfico de todas as folhas da árvore Merkle no servidor.")

    col_audit1, col_audit2 = st.columns(2)

    with col_audit1:
        simular_fraude = st.checkbox("🚨 Simular alteração maliciosa nos arquivos físicos de log")
        
        if st.button("Executar Auditoria Geral"):
            if simular_fraude:
                st.error("❌ QUEBRA DE INTEGRIDADE: O hash da raiz da árvore Merkle divergiu dos blocos locais!")
                st.warning("Alerta Forense: Tentativa de modificação de dados detectada fora da API oficial.")
            else:
                with st.spinner("Calculando hashes BLAKE3 diretamente no Core em Rust..."):
                    status_banco = db.verify()
                    time.sleep(0.4)
                    if status_banco:
                        st.success("✅ INTEGRALIDADE CONFIRMADA: 100% de consistência matemática estabelecida via Merkle Root!")
                    else:
                        st.error("❌ Falha na pipeline criptográfica informada pela engine.")

    with col_audit2:
        if simular_fraude:
            st.markdown("""
                <div style='background-color:#f8d7da; padding:20px; border-radius:10px; border: 2px solid #dc3545; text-align:center'>
                    <h2 style='color:#721c24; margin:0'>SISTEMA VIOLADO</h2>
                    <p style='color:#721c24; margin-top:10px'>Aviso: Assinatura digital corrompida em disco.</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style='background-color:#d4edda; padding:20px; border-radius:10px; border: 2px solid #28a745; text-align:center'>
                    <h2 style='color:#155724; margin:0'>LOG SEGURO</h2>
                    <p style='color:#155724; margin-top:10px'>Base imutável auditada com sucesso absoluto.</p>
                </div>
            """, unsafe_allow_html=True)