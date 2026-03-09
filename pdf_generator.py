import tempfile
import os
from fpdf import FPDF
from datetime import datetime

class PDF(FPDF):
    def header(self):
        # Arial bold 15
        self.set_font('Arial', 'B', 15)
        self.set_text_color(14, 105, 40) # Bizilur green
        # Title
        self.cell(0, 10, 'Bizilur - Informe de Pedidos Pendientes', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f'Fecha de emision: {datetime.now().strftime("%d/%m/%Y")}', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        # Page number
        self.cell(0, 10, 'Pagina ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

def create_pdf_report(df):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Check if df is empty
    if df.empty:
        pdf.set_font('Arial', 'I', 11)
        pdf.cell(0, 10, 'No hay datos disponibles para exportar con los filtros actuales.', 0, 1, 'C')
    else:
        # Sort data to ensure client grouping is solid
        if 'Nombre Cliente' in df.columns:
            df_sorted = df.sort_values(by=['Nombre Cliente', 'F. Pedido'])
            
            current_client = None
            for index, row in df_sorted.iterrows():
                client = str(row['Nombre Cliente'])
                
                # New Client Header
                if client != current_client:
                    if current_client is not None:
                        pdf.ln(5)
                    current_client = client
                    
                    # Client Title Bar
                    pdf.set_font('Arial', 'B', 12)
                    pdf.set_fill_color(14, 105, 40) # Bizilur green
                    pdf.set_text_color(255, 255, 255)
                    client_text = f" Cliente: {client}".encode('latin-1', 'replace').decode('latin-1')
                    pdf.cell(0, 8, client_text, 0, 1, 'L', fill=True)
                    
                    # Mini-Table Headers (Column titles for the items under this client)
                    pdf.set_font('Arial', 'B', 9)
                    pdf.set_text_color(80, 80, 80)
                    pdf.set_fill_color(240, 240, 240) # Light grey background
                    
                    pdf.cell(20, 6, "Fecha", 'B', 0, 'L', fill=True)
                    pdf.cell(30, 6, "Referencia", 'B', 0, 'L', fill=True)
                    pdf.cell(90, 6, "Descripcion", 'B', 0, 'L', fill=True)
                    pdf.cell(50, 6, "Pendiente", 'B', 1, 'R', fill=True)
                
                # Print item details in a table-like row
                pdf.set_font('Arial', '', 9)
                pdf.set_text_color(0, 0, 0)
                
                ref = str(row.get('Referencia', '')).encode('latin-1', 'replace').decode('latin-1')
                
                # Truncate description if it's too long
                raw_desc = str(row.get('Descripción', ''))
                if len(raw_desc) > 50:
                    raw_desc = raw_desc[:47] + "..."
                desc = raw_desc.encode('latin-1', 'replace').decode('latin-1')
                
                fecha = str(row.get('F. Pedido', ''))
                
                def fmt_num(val):
                    if isinstance(val, (int, float)):
                        return f"{val:,.0f}".replace(',', '.') if val.is_integer() else f"{val:,.2f}".replace(',', '.')
                    return str(val)
                    
                pendiente_cobro = row.get('Pendiente (Cobro)', 0)
                pendiente_bonif = row.get('Pendiente (Bonif)', 0)
                
                cobro_str = f"{fmt_num(pendiente_cobro)} cobro" if pendiente_cobro > 0 else ""
                bonif_str = f"{fmt_num(pendiente_bonif)} bonif." if pendiente_bonif > 0 else ""
                
                if cobro_str and bonif_str:
                    pend_text = f"{cobro_str} + {bonif_str}"
                else:
                    pend_text = cobro_str or bonif_str or "0 uds"
                
                # Calculate Y position to ensure row stays together
                # Print cells side-by-side
                pdf.cell(20, 6, fecha, 'B', 0, 'L')
                pdf.cell(30, 6, ref, 'B', 0, 'L')
                pdf.cell(90, 6, desc, 'B', 0, 'L')
                
                # Red text for pending units
                pdf.set_font('Arial', 'B', 9)
                pdf.set_text_color(220, 53, 69)
                pdf.cell(50, 6, pend_text, 'B', 1, 'R')

    # Save to a temporary file, read bytes, and clean up
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        temp_path = tmp.name
    
    pdf.output(temp_path, 'F')
    
    with open(temp_path, 'rb') as f:
        pdf_bytes = f.read()
        
    os.remove(temp_path)
    return pdf_bytes
