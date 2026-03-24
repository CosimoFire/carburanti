library(DatawRappr)
library(rdwd)
library(readr)
library(dplyr)
library(stringr)


datawrapper_auth(api_key = Sys.getenv("DATAWRAPPER_TOKEN"), overwrite = TRUE)

dw_test_key()


url <- "https://www.mimit.gov.it/images/stories/carburanti/MediaRegionaleStradale.csv"

carb <- read.csv(url,skip=1,header=T,sep=';')
carb$REGIONE[carb$REGIONE=='Bolzano']<-'Provincia Autonoma di Bolzano/Bozen'
carb$REGIONE[carb$REGIONE=='Emilia Romagna']<-'Emilia-Romagna'
carb$REGIONE[carb$REGIONE=='Trento']<-'Provincia Autonoma di Trento'
carb$REGIONE[carb$REGIONE=='Friuli Venezia Giulia']<-'Friuli-Venezia Giulia'
carb$REGIONE[carb$REGIONE=="Valle d'Aosta"]<-"Valle d'Aosta/Vallée d'Aoste"

oggi<-format(Sys.Date(), "%d/%m/%Y")


Gasolio<-carb|>filter(TIPOLOGIA=='Gasolio')
Benzina<-carb|>filter(TIPOLOGIA=='Benzina')
GPL<-carb|>filter(TIPOLOGIA=='GPL')
Metano<-carb|>filter(TIPOLOGIA=='Metano')


chart_id_gasolio<- "pg678" # ID reale della mappa

# 1) Mando i dati da R alla mappa
dw_data_to_chart(
  Gasolio,
  chart_id = chart_id_gasolio
)

# 2) Imposto quali colonne usare come chiave geografica e valore
dw_edit_chart(
  chart_id_gasolio,
  visualize = list(
    keys = list(
      geoId = "REGIONE",   # nome della colonna con i nomi delle regioni
      value = "PREZZO.MEDIO"     # colonna col valore da colorare
    )
  ),
  source_name = "MIMIT – Prezzi medi carburanti",
  source_url  = "https://www.mimit.gov.it/it/prezzo-medio-carburanti/regioni",
  intro  = paste0("Aggiornato al ", oggi, "."),
  byline = "Fonte: MIMIT - Prezzi medi carburanti"
)

# 3) Pubblico la mappa
dw_publish_chart(chart_id_gasolio)

##pre<-Benzina|>select(REGIONE,PREZZO.MEDIO)



chart_id_benzina<- "yBSrS"  # ID reale della mappa

# 1) Mando i dati da R alla mappa
dw_data_to_chart(
  Benzina,
  chart_id = chart_id_benzina
)

# 2) Imposto quali colonne usare come chiave geografica e valore
dw_edit_chart(
  chart_id_benzina,
  visualize = list(
    keys = list(
      geoId = "REGIONE",   # nome della colonna con i nomi delle regioni
      value = "PREZZO.MEDIO"     # colonna col valore da colorare
    )
  ),
  source_name = "MIMIT – Prezzi medi carburanti",
  source_url  = "https://www.mimit.gov.it/it/prezzo-medio-carburanti/regioni",
  intro  = paste0("Aggiornato al ", oggi, "."),
  byline = "Fonte: MIMIT - Prezzi medi carburanti"
  )

dw_publish_chart(chart_id_benzina)


chart_id_gpl<- "Cdva9"  # <-- sostituisci con l’ID reale della tua mappa

# 1) Mando i dati da R alla mappa
dw_data_to_chart(
  GPL,
  chart_id = chart_id_gpl
)

# 2) Imposto quali colonne usare come chiave geografica e valore
dw_edit_chart(
  chart_id_gpl,
  visualize = list(
    keys = list(
      geoId = "REGIONE",   # nome della colonna con i nomi delle regioni
      value = "PREZZO.MEDIO"     # colonna col valore da colorare
    )
  ),
  source_name = "MIMIT – Prezzi medi carburanti",
  source_url  = "https://www.mimit.gov.it/it/prezzo-medio-carburanti/regioni",
  intro  = paste0("Aggiornato al ", oggi, "."),
  byline = "Fonte: MIMIT - Prezzi medi carburanti"
)

# 3) Pubblico la mappa
dw_publish_chart(chart_id_gpl)



chart_id_metano<- "1gvPS"  # <-- sostituisci con l’ID reale della tua mappa

# 1) Mando i dati da R alla mappa
dw_data_to_chart(
  Metano,
  chart_id = chart_id_metano
)

# 2) Imposto quali colonne usare come chiave geografica e valore
dw_edit_chart(
  chart_id_metano,
  visualize = list(
    keys = list(
      geoId = "REGIONE",   # nome della colonna con i nomi delle regioni
      value = "PREZZO.MEDIO"     # colonna col valore da colorare
    )
  ),
  source_name = "MIMIT – Prezzi medi carburanti",
  source_url  = "https://www.mimit.gov.it/it/prezzo-medio-carburanti/regioni",
  intro  = paste0("Aggiornato al ", oggi, "."),
  byline = "Fonte: MIMIT - Prezzi medi carburanti"
)

# 3) Pubblico la mappa
dw_publish_chart(chart_id_metano)
