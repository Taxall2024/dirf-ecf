import streamlit as st
import pandas as pd
import re
from io import StringIO

st.set_page_config(page_title="Analisador DIRF + SPED ECF", layout="wide")
st.title("Cruzamento de Dados: DIRF e SPED ECF")

# ========== FUNÇÃO PARA PROCESSAR ARQUIVO DIRF ========== #
def process_dirf_file(uploaded_file):
    content = uploaded_file.read().decode("latin-1")
    linhas_dados = []

    for linha in content.splitlines():
        match = re.match(r"^(\d{14})\s+(\d)\s+(.*?)\s{2,}(\d{8})\s+(\d{4})\s+(\d{15})\s+(\d{15})", linha)
        if match:
            cnpj = match.group(1)
            tipo = match.group(2)
            nome_fonte = match.group(3).strip()
            data_entrega = match.group(4)
            cod_rendimento = int(match.group(5))
            valor_pago = int(match.group(6)) / 100
            irrf = int(match.group(7)) / 100

            linhas_dados.append({
                "CNPJ Fonte": cnpj,
                "Tipo": tipo,
                "Nome da Fonte Pagadora": nome_fonte,
                "Data Entrega": pd.to_datetime(data_entrega, format="%Y%m%d"),
                "Código Rendimento": cod_rendimento,
                "Valor Pago (R$)": valor_pago,
                "IRRF Retido (R$)": irrf
            })

    df = pd.DataFrame(linhas_dados)

    if not df.empty:
        def calc_pis(row):
            if row['Código Rendimento'] in [4085, 5952]:
                return round(row['IRRF Retido (R$)'] / (0.65 + 3 + 1) * 0.65, 2)
            elif row['Código Rendimento'] == 5979:
                return round(row['IRRF Retido (R$)'], 2)
            elif row['Código Rendimento'] in [6147, 6175]:
                return round(row['IRRF Retido (R$)'] / 5.85 * 0.65, 2)
            elif row['Código Rendimento'] == 6190:
                return round(row['IRRF Retido (R$)'] / 9.45 * 0.65, 2)
            else:
                return 0.0

        def calc_cofins(row):
            if row['Código Rendimento'] in [4085, 5952]:
                return round(row['IRRF Retido (R$)'] / (0.65 + 3 + 1) * 3, 2)
            elif row['Código Rendimento'] == 5960:
                return round(row['IRRF Retido (R$)'], 2)
            elif row['Código Rendimento'] in [6147, 6175]:
                return round(row['IRRF Retido (R$)'] / 5.85 * 3, 2)
            elif row['Código Rendimento'] == 6190:
                return round(row['IRRF Retido (R$)'] / 9.45 * 3, 2)
            else:
                return 0.0

        def calc_cs(row, pis, cofins):
            if row['Código Rendimento'] in [4085, 5952]:
                return round(row['IRRF Retido (R$)'] - (pis + cofins), 2)
            elif row['Código Rendimento'] == 5987:
                return round(row['IRRF Retido (R$)'], 2)
            elif row['Código Rendimento'] in [6147, 6175]:
                return round(row['IRRF Retido (R$)'] / 5.85 * 1, 2)
            elif row['Código Rendimento'] == 6190:
                return round(row['IRRF Retido (R$)'] / 9.45 * 1, 2)
            elif row['Código Rendimento'] in [8767]:
                return round(row['IRRF Retido (R$)'] / 2.2 * 1, 2)
            else:
                return 0.0

        def calc_ir(row, pis, cofins, cs):
            if row['Código Rendimento'] in [1708, 3426, 5273, 5557, 6800, 8045, 5706]:
                return round(row['IRRF Retido (R$)'], 2)
            elif row['Código Rendimento'] in [6147, 6175, 6190, 8767]:
                return round(row['IRRF Retido (R$)'] - (pis + cofins + cs), 2)
            else:
                return 0.0

        df["PIS (0,65)"] = df.apply(calc_pis, axis=1)
        df["COFINS (3,00)"] = df.apply(calc_cofins, axis=1)
        df["CS (1,00)"] = df.apply(lambda row: calc_cs(row, row["PIS (0,65)"], row["COFINS (3,00)"]), axis=1)
        df["IR (1,20 / 1,50 / 4,80)"] = df.apply(
            lambda row: calc_ir(row, row["PIS (0,65)"], row["COFINS (3,00)"], row["CS (1,00)"]), axis=1
        )
        df["VERIFICACAO"] = df["IRRF Retido (R$)"] - (
            df["PIS (0,65)"] + df["COFINS (3,00)"] + df["CS (1,00)"] + df["IR (1,20 / 1,50 / 4,80)"]
        )

    return df

# ========== FUNÇÃO PARA PROCESSAR ARQUIVO SPED ECF ========== #
def process_ecf_file(file):
    try:
        string_data = StringIO(file.getvalue().decode("utf-8"))
    except UnicodeDecodeError:
        string_data = StringIO(file.getvalue().decode("latin-1"))

    data = [line.strip().split('|') for line in string_data if line.strip()]
    df = pd.DataFrame(data)

    if not df.empty:
        df.columns = [f"col_{i}" for i in range(len(df.columns))]

    return df

# ========== INTERFACE STREAMLIT ========== #
col1, col2 = st.columns(2)

with col1:
    st.header("Upload Arquivo DIRF")
    dirf_file = st.file_uploader("Envie o arquivo .txt da DIRF", type=["txt"], key="dirf")

    if dirf_file:
        df_dirf = process_dirf_file(dirf_file)
        if not df_dirf.empty:
            st.subheader("Tabulação da DIRF")
            st.dataframe(df_dirf)
        else:
            st.warning("Nenhum dado compatível encontrado no arquivo DIRF.")

with col2:
    st.header("Upload Arquivo SPED ECF")
    ecf_file = st.file_uploader("Envie o arquivo .txt do SPED ECF", type=["txt"], key="ecf")

    if ecf_file:
        df_ecf = process_ecf_file(ecf_file)
        if not df_ecf.empty:
            st.subheader("Tabulação de Blocos do SPED ECF")
            st.dataframe(df_ecf)
        else:
            st.warning("Arquivo SPED ECF está vazio ou inválido.")

if dirf_file and ecf_file and not df_dirf.empty and not df_ecf.empty:
    st.header("")

    # ========================
    # PREPARAÇÃO ECF COM FILTRO Y570 E CÁLCULOS CORRETOS
    # ========================
    df_ecf_ajustada = df_ecf[df_ecf["col_1"] == "Y570"].copy()
    df_ecf_ajustada["col_2"] = df_ecf_ajustada["col_2"].astype(str).str.strip()

    for col in ["col_6", "col_7", "col_8"]:
        df_ecf_ajustada[col] = pd.to_numeric(df_ecf_ajustada[col].str.replace(",", ".", regex=False), errors="coerce").fillna(0.0)

    ecf_grouped = df_ecf_ajustada.groupby("col_2").agg({
        "col_6": "sum",
        "col_7": "sum",
        "col_8": "sum"
    }).reset_index()

    ecf_grouped.columns = [
        "CNPJ/CPF",
        "RENDIMENTO ECF",
        "IR ECF (1,20 / 1,50 / 4,80)",
        "CS ECF(1,00)"
    ]

    nomes_ecf = df_ecf_ajustada.groupby("col_2")["col_3"].first().to_dict()

    # ========================
    # PREPARAÇÃO DIRF
    # ========================
    df_dirf["CNPJ/CPF"] = df_dirf["CNPJ Fonte"]

    dirf_grouped = df_dirf.groupby("CNPJ/CPF").agg({
        "Nome da Fonte Pagadora": "first",
        "Data Entrega": "first",
        "Valor Pago (R$)": "sum",
        "IR (1,20 / 1,50 / 4,80)": "sum",
        "CS (1,00)": "sum"
    }).reset_index()

    dirf_grouped["Ano"] = dirf_grouped["Data Entrega"].dt.year - 1
    dirf_grouped.rename(columns={
        "Nome da Fonte Pagadora": "NOME EMPRESARIAL",
        "Data Entrega": "DATA DIRF",
        "Valor Pago (R$)": "RENDIMENTO DIRF",
        "IR (1,20 / 1,50 / 4,80)": "IR DIRF(1,20 / 1,50 / 4,80)",
        "CS (1,00)": "CS DIRF(1,00)"
    }, inplace=True)

    # ========================
    # MERGE DOS DADOS
    # ========================
    resultado = pd.merge(dirf_grouped, ecf_grouped, on="CNPJ/CPF", how="outer")

    resultado["NOME EMPRESARIAL"] = resultado.apply(
        lambda row: row["NOME EMPRESARIAL"] if pd.notna(row["NOME EMPRESARIAL"]) and row["NOME EMPRESARIAL"] != ""
        else nomes_ecf.get(row["CNPJ/CPF"], ""),
        axis=1
    )

    resultado["DATA DIRF"] = resultado["DATA DIRF"].fillna(pd.NaT)
    for col in ["RENDIMENTO DIRF", "RENDIMENTO ECF", "CS DIRF(1,00)", "CS ECF(1,00)",
                "IR DIRF(1,20 / 1,50 / 4,80)", "IR ECF (1,20 / 1,50 / 4,80)"]:
        resultado[col] = resultado[col].fillna(0)

    # ========================
    # DIFERENÇAS
    # ========================
    resultado["DIF. IR"] = resultado["IR DIRF(1,20 / 1,50 / 4,80)"] - resultado["IR ECF (1,20 / 1,50 / 4,80)"]
    resultado["DIF. CSLL"] = resultado["CS DIRF(1,00)"] - resultado["CS ECF(1,00)"]

    # ========================
    # REORDENAÇÃO DAS COLUNAS
    # ========================
    colunas_ordenadas = [
        "Ano",
        "CNPJ/CPF",
        "NOME EMPRESARIAL",
        "DATA DIRF",
        "RENDIMENTO DIRF",
        "RENDIMENTO ECF",
        "CS DIRF(1,00)",
        "CS ECF(1,00)",
        "IR DIRF(1,20 / 1,50 / 4,80)",
        "IR ECF (1,20 / 1,50 / 4,80)",
        "DIF. IR",
        "DIF. CSLL"
    ]

    resultado = resultado[colunas_ordenadas]

    # ========================
    # SOMATÓRIO FINAL (TOTAL GERAL)
    # ========================
    total_geral = resultado.select_dtypes(include='number').sum().to_dict()
    total_geral.update({
        "Ano": "",
        "CNPJ/CPF": "TOTAL GERAL",
        "NOME EMPRESARIAL": "",
        "DATA DIRF": ""
    })

    df_total = pd.DataFrame([total_geral])[resultado.columns]

    # ========================
    # EXIBIÇÃO
    # ========================
    st.subheader("Consolidação por CNPJ/CPF")
    st.dataframe(resultado)

    st.subheader("Total Geral")
    st.dataframe(df_total)

    # ========================
    # EXPORTAÇÃO PARA EXCEL
    # ========================
    from io import BytesIO

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        resultado.to_excel(writer, index=False, sheet_name="Consolidado")
        df_dirf.to_excel(writer, index=False, sheet_name="DIRF")
        df_ecf.to_excel(writer, index=False, sheet_name="ECF")     
    output.seek(0)

    st.download_button(
        label="📥 Exportar Tabelas para Excel",
        data=output,
        file_name="analise_dirf_ecf.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
