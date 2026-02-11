package main

import (
	"log"
	"strings"
	"time"

	"github.com/gin-contrib/sessions"
	"github.com/gin-gonic/gin"
)

const (
	// SessionTTL definisce il timeout della sessione in secondi (5 minuti, come backend Python)
	SessionTTL = 300
)

// SessionMiddleware verifica la validità della sessione basandosi sul TTL
func SessionMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		session := sessions.Default(c)

		// Verifica TTL
		if timestamp := session.Get("timestamp"); timestamp != nil {
			if ts, ok := timestamp.(int64); ok {
				if time.Now().Unix()-ts > SessionTTL {
					// Sessione scaduta, pulisci
					session.Clear()
					if err := session.Save(); err != nil {
						log.Printf("SESSION_CLEAR_ERROR: %v", err)
					}
					log.Printf("SESSION_EXPIRED: cleared expired session")
				}
			}
		}

		c.Next()
	}
}

// SaveUserSession salva i parametri utente nella sessione
func SaveUserSession(c *gin.Context, userID, aslID, aslName, cf, username string) error {
	session := sessions.Default(c)

	// Salva solo parametri non vuoti
	if userID != "" {
		session.Set("user_id", userID)
	}
	if aslID != "" {
		session.Set("asl_id", aslID)
	}
	if aslName != "" {
		session.Set("asl_name", aslName)
	}
	if cf != "" {
		session.Set("codice_fiscale", cf)
	}
	if username != "" {
		session.Set("username", username)
	}

	// Aggiorna timestamp
	session.Set("timestamp", time.Now().Unix())

	// Salva sessione
	if err := session.Save(); err != nil {
		log.Printf("SESSION_SAVE_ERROR: %v", err)
		return err
	}

	log.Printf("SESSION_SAVED: user_id=%s, asl_name=%s, asl_id=%s", userID, aslName, aslID)
	return nil
}

// GetUserSession recupera i parametri utente dalla sessione
func GetUserSession(c *gin.Context) (userID, aslID, aslName, cf, username string) {
	session := sessions.Default(c)

	// Helper per type assertion sicura
	getString := func(key string) string {
		if val := session.Get(key); val != nil {
			if str, ok := val.(string); ok {
				return str
			}
		}
		return ""
	}

	return getString("user_id"),
		getString("asl_id"),
		getString("asl_name"),
		getString("codice_fiscale"),
		getString("username")
}

// MergeSessionParams fonde parametri da query/POST con quelli salvati in sessione
// Priorità: Query/POST > Sessione
// Salva automaticamente i parametri aggiornati in sessione
func MergeSessionParams(c *gin.Context) (userID, aslID, aslName, cf, username string) {
	// Prima leggi dalla sessione (valori di default)
	userID, aslID, aslName, cf, username = GetUserSession(c)

	// Sovrascrivi con parametri dalla query string se presenti
	if queryUserID := c.Query("user_id"); queryUserID != "" {
		userID = queryUserID
	}
	if queryAslID := c.Query("asl_id"); queryAslID != "" {
		aslID = queryAslID
	}
	if queryAslName := c.Query("asl_name"); queryAslName != "" {
		aslName = queryAslName
	}
	if queryCF := c.Query("codice_fiscale"); queryCF != "" {
		cf = queryCF
	}
	if queryUsername := c.Query("username"); queryUsername != "" {
		username = queryUsername
	}

	// Se POST, controlla anche il body (JSON o form)
	if c.Request.Method == "POST" {
		contentType := c.GetHeader("Content-Type")

		if strings.Contains(contentType, "application/json") {
			// Parse JSON body
			var postParams struct {
				UserID        string `json:"user_id"`
				AslID         string `json:"asl_id"`
				AslName       string `json:"asl_name"`
				CodiceFiscale string `json:"codice_fiscale"`
			}
			// Usa ShouldBindJSON che non consuma il body
			if err := c.ShouldBindJSON(&postParams); err == nil {
				if postParams.UserID != "" {
					userID = postParams.UserID
				}
				if postParams.AslID != "" {
					aslID = postParams.AslID
				}
				if postParams.AslName != "" {
					aslName = postParams.AslName
				}
				if postParams.CodiceFiscale != "" {
					cf = postParams.CodiceFiscale
				}
			}
		} else {
			// Parse form data
			if postUserID := c.PostForm("user_id"); postUserID != "" {
				userID = postUserID
			}
			if postAslID := c.PostForm("asl_id"); postAslID != "" {
				aslID = postAslID
			}
			if postAslName := c.PostForm("asl_name"); postAslName != "" {
				aslName = postAslName
			}
			if postCF := c.PostForm("codice_fiscale"); postCF != "" {
				cf = postCF
			}
			// username è intenzionalmente ignorato da POST
		}
	}

	// Salva i parametri aggiornati in sessione
	SaveUserSession(c, userID, aslID, aslName, cf, username)

	return
}
