"""Conversão da planilha em PDF usando o Microsoft Excel (somente Windows).

O pywin32 é importado só aqui, na hora de gerar o PDF. Assim o resto do
sistema (e os testes) funcionam em qualquer computador.
"""

import os


def exportar_pdf(caminho_excel, caminho_pdf):
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return False, ("A geração do PDF usa o Microsoft Excel e só funciona no Windows "
                       f"(com o pywin32 instalado).\nA planilha foi salva em:\n{caminho_excel}")

    # INICIALIZA O COM NA NOVA THREAD (CRÍTICO PARA NÃO TRAVAR O PROGRAMA)
    pythoncom.CoInitialize() 
    excel = None
    workbook = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False 
        excel.Interactive = False 
        excel.ScreenUpdating = False 
        
        workbook = excel.Workbooks.Open(caminho_excel)
        workbook.ActiveSheet.ExportAsFixedFormat(0, caminho_pdf)
        workbook.Close(False)
        sucesso, msg = True, caminho_pdf
    except Exception as e:
        sucesso, msg = False, str(e)
    finally:
        if workbook:
            try: del workbook
            except: pass
        if excel:
            try:
                excel.Quit()
                del excel
            except: pass
        if os.path.exists(caminho_excel):
            try: os.remove(caminho_excel)
            except Exception: pass
        # DESLIGA O COM DA NOVA THREAD
        pythoncom.CoUninitialize() 
    return sucesso, msg
