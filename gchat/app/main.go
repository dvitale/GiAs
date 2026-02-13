package main

import (
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"strconv"
	"strings"

	"github.com/gin-contrib/sessions"
	"github.com/gin-contrib/sessions/cookie"
	"github.com/gin-gonic/gin"
)

func buildHierarchyHTML(descrizione string) template.HTML {
	if descrizione == "" {
		return ""
	}

	// Split by "->" separator
	parts := strings.Split(descrizione, "->")
	if len(parts) == 0 {
		return ""
	}

	// Build nested <ul><li> structure
	var html strings.Builder
	for i, part := range parts {
		part = strings.TrimSpace(part)
		html.WriteString("<li>")
		// HTML escape the content to prevent injection
		html.WriteString(template.HTMLEscapeString(part))
		if i < len(parts)-1 {
			html.WriteString("<ul>\n")
		}
	}

	// Close all nested tags (close </li> for last element, then close all </ul></li> pairs)
	html.WriteString("</li>")
	for i := len(parts) - 2; i >= 0; i-- {
		html.WriteString("</ul></li>")
	}

	return template.HTML(html.String())
}

// loadUserData loads user data from CSV by user_id and returns template-ready gin.H.
// aslName from query string takes precedence over the CSV value.
func loadUserData(userIDStr, aslName, logPrefix string) gin.H {
	if userIDStr == "" {
		return nil
	}
	userID, err := strconv.Atoi(userIDStr)
	if err != nil {
		log.Printf("%s_USER_ID_PARSE_ERROR: user_id=%s, error=%v", logPrefix, userIDStr, err)
		return nil
	}
	personale, err := GetPersonaleByUserID(userID)
	if err != nil {
		log.Printf("%s_USER_DATA_ERROR: user_id=%d, error=%v", logPrefix, userID, err)
		return nil
	}
	userASL := personale.ASL
	if aslName != "" {
		userASL = aslName
	}
	hierarchy := buildHierarchyHTML(personale.Descrizione)
	log.Printf("%s_USER_DATA_LOADED: user_id=%d, name=%s %s", logPrefix, userID, strings.ToUpper(personale.NameFirst), strings.ToUpper(personale.NameLast))
	return gin.H{
		"user_id":        userID,
		"namefirst":      strings.ToUpper(personale.NameFirst),
		"namelast":       strings.ToUpper(personale.NameLast),
		"descrizione":    personale.Descrizione,
		"asl":            userASL,
		"codice_fiscale": personale.CodiceFiscale,
		"hierarchy":      hierarchy,
	}
}

// parseQueryParams extracts common query parameters from the request.
func parseQueryParams(c *gin.Context) (userIDStr, aslID, aslName, codiceFiscale, username string) {
	return c.Query("user_id"), c.Query("asl_id"), c.Query("asl_name"), c.Query("codice_fiscale"), c.Query("username")
}

func main() {
	config := LoadConfig()

	r := gin.Default()

	// Session store setup (cookie-based)
	// IMPORTANTE: in produzione usare una chiave segreta da variabile d'ambiente
	store := cookie.NewStore([]byte("gias-secret-key-32-bytes-long!!!"))
	store.Options(sessions.Options{
		Path:     "/gias/webchat",
		MaxAge:   SessionTTL, // 5 minuti
		HttpOnly: true,
		Secure:   false, // true in produzione con HTTPS
		SameSite: http.SameSiteLaxMode,
	})

	// Apply session middleware
	r.Use(sessions.Sessions("gias_session", store))
	r.Use(SessionMiddleware())

	// Add template functions
	r.SetFuncMap(template.FuncMap{
		"json": func(v interface{}) template.JS {
			if v == nil {
				return template.JS("null")
			}
			if data, err := json.Marshal(v); err == nil {
				return template.JS(data)
			}
			return template.JS("null")
		},
	})

	r.LoadHTMLGlob("template/*")

	// Base path for reverse proxy
	basePath := "/gias/webchat"

	// Group routes under base path
	api := r.Group(basePath)
	api.Static("/static", "./statics")

	// Main page handler - supports both GET (querystring), POST (JSON body), and session
	indexHandler := func(c *gin.Context) {
		// Merge parameters: Session + Query + POST (priority: POST > Query > Session)
		userIDStr, aslID, aslName, codiceFiscale, username := MergeSessionParams(c)

		log.Printf("INDEX_REQUEST [%s]: user_id=%s, asl_id=%s, asl_name=%s, codice_fiscale=%s, username=%s, client_ip=%s (from session or params)",
			c.Request.Method, userIDStr, aslID, aslName, codiceFiscale, username, c.ClientIP())

		// Ottieni anno corrente dal server
		currentYear, err := GetCurrentYearFromServer(config.LLMServer.URL)
		welcomeMessage := config.UI.WelcomeMessage

		if err != nil {
			log.Printf("WARN: Impossibile ottenere anno dal server: %v, uso messaggio di default", err)
		} else {
			// Aggiorna il messaggio di welcome con l'anno dinamico
			welcomeMessage = strings.ReplaceAll(welcomeMessage, "**Anno 2025**", fmt.Sprintf("**Anno %d**", currentYear))
			welcomeMessage = strings.ReplaceAll(welcomeMessage, "Anno di riferimento: 2025", fmt.Sprintf("Anno di riferimento: %d", currentYear))
			welcomeMessage = strings.ReplaceAll(welcomeMessage, "Priorità 2025:", fmt.Sprintf("Priorità %d:", currentYear))
		}

		// Default template data
		templateData := gin.H{
			"title":                "Assistente Gisa",
			"user":                 nil,
			"welcomeMessage":       welcomeMessage,
			"basePath":             basePath,
			"transcriptionEnabled": config.Transcription.Enabled,
			"streamingEnabled":     config.UI.EnableStreaming,
			"queryParams": gin.H{
				"asl_id":         aslID,
				"asl_name":       aslName,
				"user_id":        userIDStr,
				"codice_fiscale": codiceFiscale,
				"username":       username,
			},
		}

		// If user_id is provided, try to load user data
		if userData := loadUserData(userIDStr, aslName, "INDEX"); userData != nil {
			templateData["user"] = userData
		}

		c.HTML(http.StatusOK, "index.html", templateData)
	}

	// Register handler for both GET and POST methods
	api.GET("/", indexHandler)
	api.POST("/", indexHandler)

	api.POST("/chat", HandleChat)
	api.POST("/chat/stream", HandleChatStream)
	api.GET("/api/predefined-questions", HandlePredefinedQuestions)
	api.POST("/api/transcribe", TranscribeHandler)

	// Debug mode endpoints
	api.GET("/debug", func(c *gin.Context) {
		userIDStr, aslID, aslName, codiceFiscale, username := MergeSessionParams(c)
		log.Printf("DEBUG_PAGE_REQUEST: user_id=%s, asl_id=%s, asl_name=%s, client_ip=%s (from session or params)",
			userIDStr, aslID, aslName, c.ClientIP())

		// Ottieni status backend con nome modello LLM
		backendStatus := GetBackendStatus()

		templateData := gin.H{
			"title":          "Assistente Gias - Debug Mode",
			"user":           loadUserData(userIDStr, aslName, "DEBUG"),
			"welcomeMessage": "Modalità Debug Attiva - Visualizza Intent, Entities e Slot",
			"basePath":       basePath,
			"llmModel":       backendStatus.LLM,
			"framework":      backendStatus.Framework,
			"queryParams": gin.H{
				"asl_id": aslID, "asl_name": aslName, "user_id": userIDStr,
				"codice_fiscale": codiceFiscale, "username": username,
			},
		}
		c.HTML(http.StatusOK, "debug.html", templateData)
	})

	// LangGraph Visualizer endpoint
	api.GET("/debug/langgraph", func(c *gin.Context) {
		userIDStr, aslID, aslName, codiceFiscale, username := MergeSessionParams(c)
		log.Printf("LANGGRAPH_DEBUG_REQUEST: user_id=%s, asl_id=%s, asl_name=%s, client_ip=%s (from session or params)",
			userIDStr, aslID, aslName, c.ClientIP())

		// Ottieni status backend con nome modello LLM
		backendStatus := GetBackendStatus()

		templateData := gin.H{
			"title":          "GIAS LangGraph Debugger",
			"user":           loadUserData(userIDStr, aslName, "LANGGRAPH"),
			"welcomeMessage": "LangGraph Workflow Visualizer - Monitor real-time execution flow",
			"basePath":       basePath,
			"llmModel":       backendStatus.LLM,
			"framework":      backendStatus.Framework,
			"queryParams": gin.H{
				"asl_id": aslID, "asl_name": aslName, "user_id": userIDStr,
				"codice_fiscale": codiceFiscale, "username": username,
			},
		}
		c.HTML(http.StatusOK, "debug_langgraph.html", templateData)
	})

	api.POST("/debug/chat", HandleDebugChat)

	// Chat Analytics Dashboard
	api.GET("/analytics", func(c *gin.Context) {
		userIDStr, aslID, aslName, codiceFiscale, username := MergeSessionParams(c)
		log.Printf("ANALYTICS_PAGE_REQUEST: user_id=%s, asl_id=%s, asl_name=%s, client_ip=%s",
			userIDStr, aslID, aslName, c.ClientIP())

		templateData := gin.H{
			"title":      "GIAS Chat Analytics",
			"user":       loadUserData(userIDStr, aslName, "ANALYTICS"),
			"basePath":   basePath,
			"backendUrl": config.LLMServer.URL,
			"queryParams": gin.H{
				"asl_id": aslID, "asl_name": aslName, "user_id": userIDStr,
				"codice_fiscale": codiceFiscale, "username": username,
			},
		}
		c.HTML(http.StatusOK, "analytics.html", templateData)
	})

	// Conversation Quality Monitor Dashboard
	api.GET("/monitor", func(c *gin.Context) {
		userIDStr, aslID, aslName, codiceFiscale, username := MergeSessionParams(c)
		log.Printf("MONITOR_PAGE_REQUEST: user_id=%s, asl_id=%s, asl_name=%s, client_ip=%s",
			userIDStr, aslID, aslName, c.ClientIP())

		templateData := gin.H{
			"title":      "GIAS Problems Monitor",
			"user":       loadUserData(userIDStr, aslName, "MONITOR"),
			"basePath":   basePath,
			"backendUrl": config.LLMServer.URL,
			"queryParams": gin.H{
				"asl_id": aslID, "asl_name": aslName, "user_id": userIDStr,
				"codice_fiscale": codiceFiscale, "username": username,
			},
		}
		c.HTML(http.StatusOK, "monitor.html", templateData)
	})

	port := config.Server.Port
	if port == "" {
		port = "8080"
	}

	log.Printf("Server starting on port %s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatal("Failed to start server:", err)
	}
}
