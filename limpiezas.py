import pandas as pd

df=pd.read_excel("3_hojas_1000_registros_sucios.xlsx",sheet_name="Ventas_sucias")

df["Cliente"]=df["Cliente"].str.strip()
df.to_excel("Ventas_limpias.xlsx",index=False)