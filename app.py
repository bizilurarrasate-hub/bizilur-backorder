import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import warnings
import altair as alt
from pdf_generator import create_pdf_report

import os

st.set_page_config(page_title="Panel de pedidos pendientes de Bizilur", layout="wide")

st.title("Panel de pedidos pendientes de Bizilur")

if os.path.exists("logo.png"):
    st.image("logo.png", width=150)
elif os.path.exists("logo.jpg"):
    st.image("logo.jpg", width=150)

# CSS Injector for Accessibility & Buttons
st.markdown("""
<style>
    /* Aumentar tamaño de botones y cambiar colores para mayor visibilidad */
    .stDownloadButton button {
        font-size: 1.15rem !important;
        padding: 0.8rem 1.5rem !important;
        height: auto !important;
        font-weight: bold !important;
        background-color: #0E6928 !important;
        color: white !important;
        border-radius: 8px !important;
    }
    .stDownloadButton button:hover {
        background-color: #0b511e !important;
        color: white !important;
    }
    
    /* Hacer el menú hamburguesa superior más grande e intuitivo */
    header[data-testid="stHeader"] {
        height: 4rem;
    }
    [data-testid="stToolbar"] button {
        transform: scale(1.4);
        transform-origin: top right;
        margin-right: 15px;
        margin-top: 10px;
    }

    /* Aumentar la fuente general de las métricas */
    [data-testid="stMetricValue"] {
        font-size: 2.5rem !important;
        color: #0E6928;
    }
    
    /* Traducir componentes internos de Streamlit que están en inglés por defecto */
    [data-testid='stFileUploadDropzone'] div div::before {
        content: 'Arrastra y suelta el archivo Excel aquí';
        color: inherit;
        display: block;
        margin-bottom: 5px;
        font-weight: 500;
    }
    [data-testid='stFileUploadDropzone'] div div span {
        display: none;
    }
    [data-testid='stFileUploadDropzone'] div div small::before {
        content: 'Límite: 200MB • xlsx';
        font-size: 14px;
        display: block;
    }
    [data-testid='stFileUploadDropzone'] div div small {
        font-size: 0;
    }
</style>
""", unsafe_allow_html=True)

uploaded_file = st.sidebar.file_uploader("Subir archivo Excel", type=["xlsx"])

def parse_spanish_numbers(x):
    if pd.isna(x):
        return 0
    if isinstance(x, str):
        x = x.replace('.', '').replace(',', '.')
    try:
        return pd.to_numeric(x)
    except:
        return x

@st.cache_data(show_spinner="Procesando archivo...")
def process_data(file_bytes):
    df = pd.read_excel(io.BytesIO(file_bytes))
    
    # Ensure all required columns are used including price indicators if available
    # Sometimes Excel uses 'Precio', 'Importe', or 'Total'
    price_cols = [c for c in df.columns if str(c).lower() in ['precio', 'importe', 'total']]
    
    required_cols_base = ['Nombre Cliente', 'Referencia', 'Descripción', 'Unidades', 'Recibidas', 'F. Pedido']
    # Keep price columns for calculation
    keep_cols = required_cols_base + price_cols
    
    missing_cols = [col for col in required_cols_base if col not in df.columns]
    if missing_cols:
        return None, missing_cols
        
    df = df[keep_cols].copy()
    
    # Filter out descriptions that contain "COMENTARIO"
    # Ensure it's a string, uppercase it, and check for the word
    mask_comentario = df['Descripción'].astype(str).str.upper().str.contains('COMENTARIO', na=False)
    df = df[~mask_comentario]
    
    df['F. Pedido Parsed'] = pd.to_datetime(df['F. Pedido'], format='%d/%m/%y', errors='coerce')
    mask = df['F. Pedido Parsed'].isna() & df['F. Pedido'].notna()
    if mask.any():
        df.loc[mask, 'F. Pedido Parsed'] = pd.to_datetime(df.loc[mask, 'F. Pedido'], dayfirst=True, errors='coerce')
        
    two_years_ago = pd.Timestamp(datetime.now() - timedelta(days=2*365))
    df = df[df['F. Pedido Parsed'] >= two_years_ago]
    
    df['Unidades'] = df['Unidades'].apply(parse_spanish_numbers)
    df['Recibidas'] = df['Recibidas'].apply(parse_spanish_numbers)
    df['Unidades'] = df['Unidades'].fillna(0)
    df['Recibidas'] = df['Recibidas'].fillna(0)
    
    # Process prices if available to detect bonuses
    has_price = len(price_cols) > 0
    if has_price:
        primary_price_col = price_cols[0]
        df['Precio_Num'] = df[primary_price_col].apply(parse_spanish_numbers).fillna(0)
        # Assuming units with Price == 0 are bonuses
        is_bonus = df['Precio_Num'] == 0
    else:
        # If no price data, assume everything is standard
        is_bonus = pd.Series(False, index=df.index)
        
    # Calculate totals
    df['Pendiente (Total)'] = df['Unidades'] - df['Recibidas']
    df['Pendiente (Cobro)'] = 0
    df['Pendiente (Bonif)'] = 0
    
    # Split them based on whether it is a bonus line or not
    # If the user uploads separate lines for bonuses
    df.loc[~is_bonus, 'Pendiente (Cobro)'] = df.loc[~is_bonus, 'Pendiente (Total)']
    df.loc[is_bonus, 'Pendiente (Bonif)'] = df.loc[is_bonus, 'Pendiente (Total)']
    
    return df, []

if uploaded_file is not None:
    st.session_state['file_bytes'] = uploaded_file.getvalue()

if 'file_bytes' in st.session_state:
    try:
        df, missing_cols = process_data(st.session_state['file_bytes'])
        
        if missing_cols:
            st.error(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
            st.stop()
        
        # --- Interactive Features ---
        
        st.sidebar.header("Filtros", help="Utiliza estos controles para reducir los datos mostrados en el panel y en el PDF exportado.")
        
        client_list = df['Nombre Cliente'].dropna().unique().tolist()
        selected_clients = st.sidebar.multiselect(
            "Seleccionar Cliente(s)", 
            client_list, 
            default=[],
            placeholder="Elige uno o varios...",
            help="Si lo dejas vacío, se mostrarán los datos de todos los clientes. Si seleccionas alguno, la tabla y los indicadores se recalcularán solo para esos clientes."
        )
        
        # Siempre la fecha actual como defecto
        today_date = datetime.now().date()
        min_date = df['F. Pedido Parsed'].min().date() if not df['F. Pedido Parsed'].empty else today_date
        max_date = df['F. Pedido Parsed'].max().date() if not df['F. Pedido Parsed'].empty else today_date
        
        date_range = st.sidebar.date_input(
            "Seleccionar Rango de Fechas",
            value=(today_date, today_date),
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",
            help="Filtra los pedidos basándose en el momento en el que se registraron en el sistema (F. Pedido)."
        )
        
        # Filtering dataset
        if selected_clients:
            filtered_df = df[df['Nombre Cliente'].isin(selected_clients)]
        else:
            filtered_df = df.copy()
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            mask = (filtered_df['F. Pedido Parsed'].dt.date >= start_date) & (filtered_df['F. Pedido Parsed'].dt.date <= end_date)
            filtered_df = filtered_df.loc[mask]
        
        # Clean dataframe for display
        # Format date as string for display
        filtered_df['F. Pedido Str'] = filtered_df['F. Pedido Parsed'].dt.strftime('%d/%m/%Y')
        display_cols = ['Nombre Cliente', 'Referencia', 'Descripción', 'F. Pedido Str', 'Unidades', 'Recibidas', 'Pendiente (Total)', 'Pendiente (Cobro)', 'Pendiente (Bonif)']
        display_df = filtered_df[display_cols].rename(columns={'F. Pedido Str': 'F. Pedido'})
        
        # KPI Cards
        st.subheader("Indicadores Clave de Rendimiento", help="Resumen global de la situación actual basado en los filtros seleccionados.")
        col1, col2 = st.columns(2)
        
        total_pending = display_df['Pendiente (Total)'].sum()
        total_paid_pending = display_df['Pendiente (Cobro)'].sum()
        total_bonus_pending = display_df['Pendiente (Bonif)'].sum()
        
        most_affected_client = "N/A"
        if not display_df.empty:
            client_agg = display_df.groupby('Nombre Cliente')['Pendiente (Total)'].sum().sort_values(ascending=False)
            if not client_agg.empty and client_agg.iloc[0] > 0:
                most_affected_client = f"{client_agg.index[0]} ({client_agg.iloc[0]:,.0f} uds)".replace(',', '.')
                
        with col1:
            st.metric(
                "Total de Unidades Pendientes", 
                f"{total_pending:,.0f}".replace(',', '.'), 
                delta=f"{total_paid_pending:,.0f} cobro + {total_bonus_pending:,.0f} bonif.", 
                delta_color="off",
                help="Suma total de unidades que el proveedor aún no ha entregado (Unidades Pedidas - Unidades Recibidas). El desglose inferior separa las unidades que se cobran de las que son bonificaciones (precio 0)."
            )
        with col2:
            st.metric(
                "Cliente Principal", 
                most_affected_client,
                help="El cliente individual que acumula el mayor volumen de unidades pendientes de entrega en este momento."
            )
            
        st.markdown("---")
        
        # --- Advanced Analytics for Purchasing Manager ---
        st.subheader("Análisis de Compras y Roturas de Stock")
        
        if not display_df.empty:
            st.markdown("##### Artículos Críticos (Mayor volumen pendiente)")
            
            # Control para que el usuario elija cuántos elementos ver
            top_n = st.slider(
                "Cantidad de artículos a mostrar en el Top", 
                min_value=5, max_value=50, value=10, step=5,
                help="Desliza para ampliar o reducir la cantidad de artículos que aparecen en el gráfico."
            )
            
            # Agrupar solo por Descripción (sin Referencia/SKU)
            top_refs = filtered_df.groupby('Descripción')['Pendiente (Total)'].sum().reset_index()
            top_refs = top_refs[top_refs['Pendiente (Total)'] > 0]
            top_refs = top_refs.sort_values('Pendiente (Total)', ascending=False).head(top_n)
            
            if not top_refs.empty:
                # Recortar textos muy largos para que no rompan el gráfico
                top_refs['Articulo'] = top_refs['Descripción'].astype(str).str.slice(0, 50) + "..."
                
                bar_chart = alt.Chart(top_refs).mark_bar(color='#20c997', cornerRadiusEnd=4).encode(
                    x=alt.X('Pendiente (Total):Q', title='Unidades Pendientes'),
                    y=alt.Y('Articulo:N', sort='-x', title=None, axis=alt.Axis(labelLimit=400)),
                    tooltip=[
                        alt.Tooltip('Descripción', title='Descripción Completa'), 
                        alt.Tooltip('Pendiente (Total)', title='Unidades Pendientes')
                    ]
                ).properties(
                    height=max(300, top_n * 25) # Escalar la altura dinámicamente según el número de barras
                ).configure_view(strokeWidth=0)
                
                st.altair_chart(bar_chart, use_container_width=True)
                
        st.markdown("---")
            
        # Clean Table Display
        st.subheader("Datos Detallados de Pedidos")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # PDF Reporting
        pdf_bytes = create_pdf_report(display_df)
        st.download_button(
            label="Descargar Informe en PDF",
            data=pdf_bytes,
            file_name="bizilur_informe_pendientes.pdf",
            mime="application/pdf"
        )
            
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
        
else:
    st.info("Por favor, suba un archivo Excel para comenzar. Nota: Las filas con 'F. Pedido' de antigüedad mayor a 2 años serán excluidas automáticamente.")
