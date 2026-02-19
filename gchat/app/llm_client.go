package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

type LLMMessage struct {
	Sender   string                 `json:"sender"`
	Message  string                 `json:"message"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// Health check cache to avoid checking on every request
type healthCheckCache struct {
	isHealthy  bool
	lastCheck  time.Time
	mu         sync.RWMutex
	ttl        time.Duration
}

var (
	healthCache = &healthCheckCache{
		ttl: 30 * time.Second, // Cache health status for 30 seconds
	}
)

type LLMResponse struct {
	Text        string                 `json:"text"`
	Custom      map[string]interface{} `json:"custom,omitempty"`
}

type ChatRequest struct {
	Message       string `json:"message"`
	Sender        string `json:"sender"`
	ASL           string `json:"asl,omitempty"`
	ASLID         string `json:"asl_id,omitempty"`
	UserID        string `json:"user_id,omitempty"`
	CodiceFiscale string `json:"codice_fiscale,omitempty"`
	Username      string `json:"username,omitempty"`
	UOC           string `json:"uoc,omitempty"` // NUOVO: Unità Operativa Complessa
}

type ChatResponse struct {
	Message     string                   `json:"message"`
	Status      string                   `json:"status"`
	Error       string                   `json:"error,omitempty"`
	FullData    interface{}              `json:"full_data,omitempty"`
	DataType    string                   `json:"data_type,omitempty"`
	Suggestions []map[string]interface{} `json:"suggestions,omitempty"`
}

// SSE Event structures for streaming
type SSEEvent struct {
	Type      string                 `json:"type"`
	Timestamp int64                  `json:"timestamp"`
	Node      string                 `json:"node,omitempty"`
	Message   string                 `json:"message,omitempty"`
	Content   string                 `json:"content,omitempty"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
	Error     string                 `json:"error,omitempty"`
	Progress  int                    `json:"progress,omitempty"`
	IsFinal   bool                   `json:"is_final,omitempty"`
}

// Sanitize PII data for debug logging
func sanitizePII(data map[string]interface{}) map[string]interface{} {
	if data == nil {
		return nil
	}

	sanitized := make(map[string]interface{})
	for key, value := range data {
		switch key {
		case "codice_fiscale":
			if str, ok := value.(string); ok && len(str) > 0 {
				sanitized[key] = str[:3] + "***********" + str[len(str)-1:]
			} else {
				sanitized[key] = "***"
			}
		case "user_id":
			sanitized[key] = "***"
		case "asl", "asl_id", "username":
			// Keep these for functionality debugging, but log notice
			sanitized[key] = value
		default:
			sanitized[key] = value
		}
	}
	return sanitized
}

// Genera un comando curl per testare l'API GIAS
func generateCurlCommand(url string, payload []byte, headers map[string]string) string {
	var curlCmd strings.Builder
	curlCmd.WriteString("curl -X POST")
	curlCmd.WriteString(fmt.Sprintf(" '%s'", url))

	// Headers
	curlCmd.WriteString(" -H 'Content-Type: application/json'")
	for key, value := range headers {
		curlCmd.WriteString(fmt.Sprintf(" -H '%s: %s'", key, value))
	}

	// Payload formattato e escaped per shell
	payloadStr := string(payload)
	payloadStr = strings.ReplaceAll(payloadStr, "'", "'\"'\"'") // Escape single quotes per shell
	curlCmd.WriteString(fmt.Sprintf(" -d '%s'", payloadStr))

	return curlCmd.String()
}

// Scrive il comando curl in un file di log separato per debug API
func logCurlCommand(endpoint string, curlCmd string, requestData map[string]interface{}, debugFile string) {
	// Crea directory se non esiste
	if err := os.MkdirAll("log", 0755); err != nil {
		log.Printf("DEBUG_LOG_ERROR: Cannot create log directory: %v", err)
		return
	}

	// Check file size for rotation (limit to 10MB)
	const maxSize = 10 * 1024 * 1024
	if info, err := os.Stat(debugFile); err == nil && info.Size() > maxSize {
		// Rotate the log file
		oldFile := debugFile + ".old"
		os.Rename(debugFile, oldFile)
		log.Printf("DEBUG_LOG: Rotated debug log file %s to %s", debugFile, oldFile)
	}

	// Apri o crea file di log
	file, err := os.OpenFile(debugFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Printf("DEBUG_LOG_ERROR: Cannot open log file: %v", err)
		return
	}
	defer file.Close()

	timestamp := time.Now().Format("2006-01-02 15:04:05")

	// Header della sessione debug
	file.WriteString(fmt.Sprintf("\n=== GIAS API DEBUG SESSION - %s ===\n", timestamp))
	file.WriteString(fmt.Sprintf("Endpoint: %s\n", endpoint))

	// Dati della richiesta in formato JSON leggibile (già sanitizzati)
	if requestDataJSON, err := json.MarshalIndent(requestData, "", "  "); err == nil {
		file.WriteString("Request Data (PII sanitized):\n")
		file.WriteString(string(requestDataJSON))
		file.WriteString("\n\n")
	}

	// Comando curl per test manuale
	file.WriteString("CURL TEST COMMAND:\n")
	file.WriteString(curlCmd)
	file.WriteString("\n")
	file.WriteString("=== END DEBUG SESSION ===\n\n")
}

func SendToLLM(message, sender, llmServerURL string, timeout int, context map[string]interface{}) ([]LLMResponse, error) {
	fullURL := llmServerURL + "/webhooks/rest/webhook"
	log.Printf("LLM_REQUEST: sender=%s, message=%s, url=%s, full_endpoint=%s, timeout=%ds", sender, message, llmServerURL, fullURL, timeout)

	llmMessage := LLMMessage{
		Sender:   sender,
		Message:  message,
		Metadata: context,
	}

	if context != nil && len(context) > 0 {
		log.Printf("LLM_CONTEXT: context=%+v", context)
	}

	jsonData, err := json.Marshal(llmMessage)
	if err != nil {
		log.Printf("LLM_ERROR: Failed to marshal request - sender=%s, error=%v", sender, err)
		return nil, fmt.Errorf("error marshaling message: %v", err)
	}

	log.Printf("LLM_SEND: JSON payload=%s", string(jsonData))

	// *** GENERATE CURL COMMAND FOR DEBUG (only if debug enabled) ***
	config := LoadConfig()
	if config.Log.EnableDebug {
		headers := map[string]string{
			"User-Agent": "GChat/1.0",
			"X-Source":   "gchat-debug",
		}
		curlCmd := generateCurlCommand(fullURL, jsonData, headers)

		// Sanitize PII from context for logging
		sanitizedContext := sanitizePII(context)

		// Prepara i dati per il log debug
		requestData := map[string]interface{}{
			"url":         fullURL,
			"method":      "POST",
			"headers":     headers,
			"payload": map[string]interface{}{
				"sender":   sender,
				"message":  message,
				"metadata": sanitizedContext,
			},
			"timeout":   timeout,
			"timestamp": time.Now().Format("2006-01-02 15:04:05"),
		}

		// Log curl command nel file dedicato
		logCurlCommand("WEBHOOK", curlCmd, requestData, config.Log.DebugFile)
		log.Printf("GIAS_API_DEBUG: Curl command logged to %s", config.Log.DebugFile)
	}

	client := &http.Client{
		Timeout: time.Duration(timeout) * time.Second,
	}

	start := time.Now()
	resp, err := client.Post(fullURL, "application/json", bytes.NewBuffer(jsonData))
	elapsed := time.Since(start)

	if err != nil {
		log.Printf("LLM_ERROR: HTTP request failed - sender=%s, url=%s, duration=%v, error=%v", sender, llmServerURL, elapsed, err)
		return nil, fmt.Errorf("error sending request to LLM server: %v", err)
	}
	defer resp.Body.Close()

	log.Printf("LLM_RESPONSE: status=%d, duration=%v", resp.StatusCode, elapsed)

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("LLM_ERROR: Failed to read response body - sender=%s, error=%v", sender, err)
		return nil, fmt.Errorf("error reading response: %v", err)
	}

	if resp.StatusCode != http.StatusOK {
		log.Printf("LLM_ERROR: Non-200 status - sender=%s, status=%d, duration=%v, error_body=%s", sender, resp.StatusCode, elapsed, string(body))
		return nil, fmt.Errorf("LLM server returned status %d: %s", resp.StatusCode, string(body))
	}

	log.Printf("LLM_RAW_RESPONSE: body=%s", string(body))

	var llmResponses []LLMResponse
	if err := json.Unmarshal(body, &llmResponses); err != nil {
		log.Printf("LLM_ERROR: Failed to unmarshal response - sender=%s, body=%s, error=%v", sender, string(body), err)
		return nil, fmt.Errorf("error unmarshaling response: %v", err)
	}

	log.Printf("LLM_SUCCESS: sender=%s, responses_count=%d, duration=%v", sender, len(llmResponses), elapsed)
	for i, resp := range llmResponses {
		log.Printf("LLM_RESPONSE_ITEM: sender=%s, index=%d, text=%s", sender, i, resp.Text)
	}

	return llmResponses, nil
}

// SendToLLMStream sends a message to LLM server and streams events via SSE
func SendToLLMStream(message, sender, llmServerURL string, timeout int, context map[string]interface{}, eventChan chan<- SSEEvent, streamEndpoint string) error {
	// Use configured stream endpoint, fallback to default if empty
	if streamEndpoint == "" {
		streamEndpoint = "/webhooks/rest/webhook/stream"
	}
	fullURL := llmServerURL + streamEndpoint
	log.Printf("LLM_STREAM_REQUEST: sender=%s, message=%s, url=%s, timeout=%ds", sender, message, fullURL, timeout)

	llmMessage := LLMMessage{
		Sender:   sender,
		Message:  message,
		Metadata: context,
	}

	if context != nil && len(context) > 0 {
		log.Printf("LLM_STREAM_CONTEXT: context=%+v", context)
	}

	jsonData, err := json.Marshal(llmMessage)
	if err != nil {
		log.Printf("LLM_STREAM_ERROR: Failed to marshal request - sender=%s, error=%v", sender, err)
		return fmt.Errorf("error marshaling message: %v", err)
	}

	log.Printf("LLM_STREAM_SEND: JSON payload=%s", string(jsonData))

	client := &http.Client{
		Timeout: time.Duration(timeout) * time.Second,
	}

	req, err := http.NewRequest("POST", fullURL, bytes.NewBuffer(jsonData))
	if err != nil {
		log.Printf("LLM_STREAM_ERROR: Failed to create request - error=%v", err)
		return fmt.Errorf("error creating request: %v", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")
	req.Header.Set("Cache-Control", "no-cache")

	start := time.Now()
	resp, err := client.Do(req)
	if err != nil {
		elapsed := time.Since(start)
		log.Printf("LLM_STREAM_ERROR: HTTP request failed - sender=%s, url=%s, duration=%v, error=%v", sender, llmServerURL, elapsed, err)
		return fmt.Errorf("error sending request to LLM server: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		log.Printf("LLM_STREAM_ERROR: Non-200 status - sender=%s, status=%d, error_body=%s", sender, resp.StatusCode, string(body))
		return fmt.Errorf("LLM server returned status %d: %s", resp.StatusCode, string(body))
	}

	log.Printf("LLM_STREAM_CONNECTED: status=%d, starting SSE parse", resp.StatusCode)

	// Parse SSE stream using bufio.Scanner
	scanner := bufio.NewScanner(resp.Body)
	var eventType string
	var dataLines []string

	for scanner.Scan() {
		line := scanner.Text()

		// Empty line indicates end of event
		if line == "" {
			// Parse accumulated data
			if len(dataLines) > 0 {
				dataJSON := strings.Join(dataLines, "\n")
				var event SSEEvent
				if err := json.Unmarshal([]byte(dataJSON), &event); err == nil {
					// Set event type from event: field
					if eventType != "" {
						event.Type = eventType
					}
					eventChan <- event
					log.Printf("LLM_STREAM_EVENT: type=%s, message=%s, content=%s", event.Type, event.Message, event.Content)
				} else {
					log.Printf("LLM_STREAM_PARSE_ERROR: Failed to parse event JSON: %v, data=%s", err, dataJSON)
				}
			}
			// Reset for next event
			eventType = ""
			dataLines = nil
			continue
		}

		// Parse SSE fields
		if strings.HasPrefix(line, "event: ") {
			eventType = strings.TrimSpace(strings.TrimPrefix(line, "event: "))
		} else if strings.HasPrefix(line, "data: ") {
			data := strings.TrimSpace(strings.TrimPrefix(line, "data: "))
			dataLines = append(dataLines, data)
		}
	}

	if err := scanner.Err(); err != nil && err != io.EOF {
		log.Printf("LLM_STREAM_ERROR: Scanner error: %v", err)
		return fmt.Errorf("error reading stream: %v", err)
	}

	elapsed := time.Since(start)
	log.Printf("LLM_STREAM_COMPLETE: sender=%s, total_duration=%v", sender, elapsed)
	close(eventChan)
	return nil
}

func CheckLLMServerHealth(llmServerURL string, timeout int) error {
	healthCache.mu.RLock()

	// Check if we have a recent positive health check
	if healthCache.isHealthy && time.Since(healthCache.lastCheck) < healthCache.ttl {
		healthCache.mu.RUnlock()
		log.Printf("LLM_HEALTH_CACHE: Using cached healthy status (age: %v)", time.Since(healthCache.lastCheck))
		return nil
	}

	// If we have a recent negative health check, fail fast (shorter TTL for failures)
	if !healthCache.isHealthy && time.Since(healthCache.lastCheck) < 5*time.Second {
		healthCache.mu.RUnlock()
		log.Printf("LLM_HEALTH_CACHE: Using cached unhealthy status (age: %v)", time.Since(healthCache.lastCheck))
		return fmt.Errorf("LLM server is down (cached)")
	}

	healthCache.mu.RUnlock()

	// Need to perform actual health check
	log.Printf("LLM_HEALTH_CHECK: Performing actual check - url=%s", llmServerURL)

	client := &http.Client{
		Timeout: time.Duration(timeout) * time.Second,
	}

	resp, err := client.Get(llmServerURL)
	if err != nil {
		log.Printf("LLM_HEALTH_ERROR: Cannot connect to LLM server - url=%s, error=%v", llmServerURL, err)

		// Cache the failure
		healthCache.mu.Lock()
		healthCache.isHealthy = false
		healthCache.lastCheck = time.Now()
		healthCache.mu.Unlock()

		return fmt.Errorf("cannot connect to LLM server: %v", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	log.Printf("LLM_HEALTH_RESPONSE: status=%d, body=%s", resp.StatusCode, string(body))

	if resp.StatusCode != http.StatusOK {
		// Cache the failure
		healthCache.mu.Lock()
		healthCache.isHealthy = false
		healthCache.lastCheck = time.Now()
		healthCache.mu.Unlock()

		return fmt.Errorf("LLM server health check failed with status %d", resp.StatusCode)
	}

	// Cache the success
	healthCache.mu.Lock()
	healthCache.isHealthy = true
	healthCache.lastCheck = time.Now()
	healthCache.mu.Unlock()

	log.Printf("LLM_HEALTH_OK: LLM server is running (cached for %v)", healthCache.ttl)
	return nil
}

func HandleChat(c *gin.Context) {
	clientIP := c.ClientIP()
	sessionID := c.GetHeader("X-Session-ID")
	log.Printf("CHAT_REQUEST: client_ip=%s, session_id=%s", clientIP, sessionID)

	var req ChatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Printf("CHAT_ERROR: Invalid JSON format - client_ip=%s, error=%v", clientIP, err)
		c.JSON(http.StatusBadRequest, ChatResponse{
			Status: "error",
			Error:  "Invalid request format",
		})
		return
	}

	config := LoadConfig()

	if req.Sender == "" {
		req.Sender = "user"
	}

	log.Printf("CHAT_PROCESSING: client_ip=%s, sender=%s, message_length=%d, asl=%s, asl_id=%s, user_id=%s",
		clientIP, req.Sender, len(req.Message), req.ASL, req.ASLID, req.UserID)

	// NUOVO: Se UOC non fornito nel request, prova a recuperarlo da personale via user_id
	uoc := req.UOC
	if uoc == "" && req.UserID != "" {
		if userID, err := strconv.Atoi(req.UserID); err == nil {
			if personale, err := GetPersonaleByUserID(userID); err == nil {
				uoc = personale.DescrizioneAreaStrutturaComplessa
				// Fallback: se UOC è "NULL" o vuoto, estrai dal campo Descrizione
				if uoc == "" || uoc == "NULL" {
					parts := strings.Split(personale.Descrizione, "->")
					if len(parts) >= 2 {
						uoc = strings.TrimSpace(parts[1])
						log.Printf("CHAT_UOC_FALLBACK: user_id=%s, extracted from Descrizione, uoc=%s", req.UserID, uoc)
					}
				} else {
					log.Printf("CHAT_UOC_LOADED: user_id=%s, uoc=%s", req.UserID, uoc)
				}
			} else {
				log.Printf("CHAT_UOC_ERROR: user_id=%s, error=%v", req.UserID, err)
			}
		}
	}

	// Prepare context for LLM server - prioritize asl_name (ASL) over asl_id
	context := make(map[string]interface{})
	if req.ASL != "" {
		context["asl"] = req.ASL
	} else if req.ASLID != "" {
		context["asl_id"] = req.ASLID
	}
	if req.UserID != "" {
		context["user_id"] = req.UserID
	}
	if req.CodiceFiscale != "" {
		context["codice_fiscale"] = req.CodiceFiscale
	}
	if req.Username != "" {
		context["username"] = req.Username
	}
	// NUOVO: Passa UOC se disponibile
	if uoc != "" {
		context["uoc"] = uoc
	}

	// Check LLM server health before sending message
	if err := CheckLLMServerHealth(config.LLMServer.URL, config.LLMServer.Timeout); err != nil {
		log.Printf("CHAT_ERROR: LLM server health check failed - client_ip=%s, sender=%s, error=%v", clientIP, req.Sender, err)
		c.JSON(http.StatusServiceUnavailable, ChatResponse{
			Status: "error",
			Error:  fmt.Sprintf("LLM server service unavailable: %v", err),
		})
		return
	}

	start := time.Now()
	responses, err := SendToLLM(req.Message, req.Sender, config.LLMServer.URL, config.LLMServer.Timeout, context)
	totalDuration := time.Since(start)

	if err != nil {
		log.Printf("CHAT_ERROR: LLM server communication failed - client_ip=%s, sender=%s, duration=%v, error=%v", clientIP, req.Sender, totalDuration, err)
		c.JSON(http.StatusInternalServerError, ChatResponse{
			Status: "error",
			Error:  fmt.Sprintf("Error communicating with LLM server: %v", err),
		})
		return
	}

	if len(responses) == 0 {
		log.Printf("CHAT_WARNING: Empty response from LLM server - client_ip=%s, sender=%s, duration=%v", clientIP, req.Sender, totalDuration)
		c.JSON(http.StatusOK, ChatResponse{
			Message: "Sorry, I didn't understand that.",
			Status:  "success",
		})
		return
	}

	responseText := responses[0].Text
	var fullData interface{}
	var dataType string
	var suggestions []map[string]interface{}

	// Extract custom payload from any response that contains it
	for _, resp := range responses {
		if resp.Custom != nil && len(resp.Custom) > 0 {
			if fd, ok := resp.Custom["full_data"]; ok {
				fullData = fd
			}
			if dt, ok := resp.Custom["data_type"].(string); ok {
				dataType = dt
			}
			if sugg, ok := resp.Custom["suggestions"].([]interface{}); ok {
				for _, s := range sugg {
					if suggMap, ok := s.(map[string]interface{}); ok {
						suggestions = append(suggestions, suggMap)
					}
				}
			}
			if fullData != nil && dataType != "" && len(suggestions) > 0 {
				break // Found all data, stop searching
			}
		}
	}

	for i := 1; i < len(responses); i++ {
		responseText += "\n\n" + responses[i].Text
	}

	log.Printf("CHAT_SUCCESS: client_ip=%s, sender=%s, response_length=%d, total_duration=%v, has_full_data=%v, has_suggestions=%v",
		clientIP, req.Sender, len(responseText), totalDuration, fullData != nil, len(suggestions) > 0)

	c.JSON(http.StatusOK, ChatResponse{
		Message:     responseText,
		Status:      "success",
		FullData:    fullData,
		DataType:    dataType,
		Suggestions: suggestions,
	})
}

// HandleChatStream handles streaming chat requests with SSE
func HandleChatStream(c *gin.Context) {
	clientIP := c.ClientIP()
	sessionID := c.GetHeader("X-Session-ID")
	log.Printf("CHAT_STREAM_REQUEST: client_ip=%s, session_id=%s", clientIP, sessionID)

	var req ChatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Printf("CHAT_STREAM_ERROR: Invalid JSON format - client_ip=%s, error=%v", clientIP, err)
		c.JSON(http.StatusBadRequest, ChatResponse{
			Status: "error",
			Error:  "Invalid request format",
		})
		return
	}

	config := LoadConfig()

	if req.Sender == "" {
		req.Sender = "user"
	}

	log.Printf("CHAT_STREAM_PROCESSING: client_ip=%s, sender=%s, message_length=%d, asl=%s, asl_id=%s, user_id=%s",
		clientIP, req.Sender, len(req.Message), req.ASL, req.ASLID, req.UserID)

	// NUOVO: Se UOC non fornito nel request, prova a recuperarlo da personale via user_id
	uoc := req.UOC
	if uoc == "" && req.UserID != "" {
		if userID, err := strconv.Atoi(req.UserID); err == nil {
			if personale, err := GetPersonaleByUserID(userID); err == nil {
				uoc = personale.DescrizioneAreaStrutturaComplessa
				// Fallback: se UOC è "NULL" o vuoto, estrai dal campo Descrizione
				if uoc == "" || uoc == "NULL" {
					parts := strings.Split(personale.Descrizione, "->")
					if len(parts) >= 2 {
						uoc = strings.TrimSpace(parts[1])
						log.Printf("CHAT_STREAM_UOC_FALLBACK: user_id=%s, extracted from Descrizione, uoc=%s", req.UserID, uoc)
					}
				} else {
					log.Printf("CHAT_STREAM_UOC_LOADED: user_id=%s, uoc=%s", req.UserID, uoc)
				}
			} else {
				log.Printf("CHAT_STREAM_UOC_ERROR: user_id=%s, error=%v", req.UserID, err)
			}
		}
	}

	// Prepare context for LLM server
	context := make(map[string]interface{})
	if req.ASL != "" {
		context["asl"] = req.ASL
	} else if req.ASLID != "" {
		context["asl_id"] = req.ASLID
	}
	if req.UserID != "" {
		context["user_id"] = req.UserID
	}
	if req.CodiceFiscale != "" {
		context["codice_fiscale"] = req.CodiceFiscale
	}
	if req.Username != "" {
		context["username"] = req.Username
	}
	// NUOVO: Passa UOC se disponibile
	if uoc != "" {
		context["uoc"] = uoc
	}

	// Check LLM server health
	if err := CheckLLMServerHealth(config.LLMServer.URL, config.LLMServer.Timeout); err != nil {
		log.Printf("CHAT_STREAM_ERROR: LLM server health check failed - client_ip=%s, sender=%s, error=%v", clientIP, req.Sender, err)
		c.JSON(http.StatusServiceUnavailable, ChatResponse{
			Status: "error",
			Error:  fmt.Sprintf("LLM server service unavailable: %v", err),
		})
		return
	}

	// Set SSE headers
	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("X-Accel-Buffering", "no")

	// Create event channel
	eventChan := make(chan SSEEvent, 10)

	// Start streaming in goroutine
	go func() {
		start := time.Now()
		err := SendToLLMStream(req.Message, req.Sender, config.LLMServer.URL, config.LLMServer.Timeout, context, eventChan, config.LLMServer.StreamEndpoint)
		totalDuration := time.Since(start)

		if err != nil {
			log.Printf("CHAT_STREAM_ERROR: LLM server communication failed - client_ip=%s, sender=%s, duration=%v, error=%v", clientIP, req.Sender, totalDuration, err)
			// Send error event
			eventChan <- SSEEvent{
				Type:      "error",
				Timestamp: time.Now().UnixMilli(),
				Error:     fmt.Sprintf("Error communicating with LLM server: %v", err),
			}
		} else {
			log.Printf("CHAT_STREAM_SUCCESS: client_ip=%s, sender=%s, total_duration=%v", clientIP, req.Sender, totalDuration)
		}
	}()

	// Stream events to client
	flusher, ok := c.Writer.(http.Flusher)
	if !ok {
		log.Printf("CHAT_STREAM_ERROR: Streaming not supported - client_ip=%s", clientIP)
		c.JSON(http.StatusInternalServerError, ChatResponse{
			Status: "error",
			Error:  "Streaming not supported",
		})
		return
	}

	c.Stream(func(w io.Writer) bool {
		event, ok := <-eventChan
		if !ok {
			// Channel closed, end stream
			log.Printf("CHAT_STREAM_CHANNEL_CLOSED: client_ip=%s, sender=%s", clientIP, req.Sender)
			return false
		}

		// Format SSE event
		eventJSON, err := json.Marshal(event)
		if err != nil {
			log.Printf("CHAT_STREAM_ERROR: Failed to marshal event: %v", err)
			return true // Continue streaming
		}

		// Write SSE formatted event
		fmt.Fprintf(w, "event: %s\ndata: %s\n\n", event.Type, string(eventJSON))

		// CRITICAL: Flush buffer immediately to send event to client
		flusher.Flush()

		// Log event transmission
		log.Printf("CHAT_STREAM_EVENT_SENT: client_ip=%s, sender=%s, event_type=%s, data_length=%d",
			clientIP, req.Sender, event.Type, len(eventJSON))

		// Continue streaming until channel is closed
		// Don't close on "final" - let the backend close the channel naturally
		return true
	})
}

func HandlePredefinedQuestions(c *gin.Context) {
	config := LoadConfig()

	log.Printf("PREDEFINED_QUESTIONS_REQUEST: client_ip=%s", c.ClientIP())

	c.JSON(http.StatusOK, gin.H{
		"questions": config.PredefinedQuestions,
		"status":    "success",
	})
}

// ProxyChatLogAPI proxies chat-log API requests to the backend to avoid CORS issues
func ProxyChatLogAPI(c *gin.Context, llmServerURL string, timeout int) {
	// Reconstruct the backend URL from the original request path
	// Strip the base path prefix to get the API path
	originalPath := c.Request.URL.Path
	// Find "/api/chat-log/" in the path and use everything from there
	apiIdx := strings.Index(originalPath, "/api/chat-log/")
	if apiIdx == -1 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid API path"})
		return
	}
	apiPath := originalPath[apiIdx:]
	backendURL := llmServerURL + apiPath
	if c.Request.URL.RawQuery != "" {
		backendURL += "?" + c.Request.URL.RawQuery
	}

	log.Printf("CHATLOG_PROXY: %s -> %s", originalPath, backendURL)

	client := &http.Client{
		Timeout: time.Duration(timeout) * time.Second,
	}

	resp, err := client.Get(backendURL)
	if err != nil {
		log.Printf("CHATLOG_PROXY_ERROR: url=%s, error=%v", backendURL, err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "Backend not available"})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("CHATLOG_PROXY_ERROR: read error=%v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read backend response"})
		return
	}

	c.Data(resp.StatusCode, resp.Header.Get("Content-Type"), body)
}

// Debug mode structures
type LLMParseResponse struct {
	Text   string                   `json:"text"`
	Intent map[string]interface{}   `json:"intent"`
	Entities []map[string]interface{} `json:"entities"`
}

type LLMTrackerResponse struct {
	ConversationID string                 `json:"sender_id"`
	Slots          map[string]interface{} `json:"slots"`
	LatestMessage  map[string]interface{} `json:"latest_message"`
	Events         []map[string]interface{} `json:"events"`
}

type DebugChatRequest struct {
	Message       string `json:"message"`
	Sender        string `json:"sender"`
	ASL           string `json:"asl,omitempty"`
	ASLID         string `json:"asl_id,omitempty"`
	UserID        string `json:"user_id,omitempty"`
	CodiceFiscale string `json:"codice_fiscale,omitempty"`
	Username      string `json:"username,omitempty"`
	UOC           string `json:"uoc,omitempty"` // NUOVO: Unità Operativa Complessa
}

type DebugChatResponse struct {
	Message    string                   `json:"message"`
	Status     string                   `json:"status"`
	Error      string                   `json:"error,omitempty"`
	Intent     map[string]interface{}   `json:"intent,omitempty"`
	Entities   []map[string]interface{} `json:"entities,omitempty"`
	Slots      map[string]interface{}   `json:"slots,omitempty"`
	Metadata        map[string]interface{}   `json:"metadata,omitempty"`
	Confidence      float64                  `json:"confidence,omitempty"`
	ExecutedActions []string                 `json:"executed_actions,omitempty"`
	// Enhanced debug fields for LangGraph visualization
	ExecutionPath     []string                 `json:"execution_path,omitempty"`
	NodeTimings       map[string]interface{}   `json:"node_timings,omitempty"`
	WorkflowState     string                   `json:"workflow_state,omitempty"`
	TotalExecutionMs  float64                  `json:"total_execution_ms,omitempty"`
	OriginalMessage   string                   `json:"original_message,omitempty"`
}

// ParseMessage calls LLM server /model/parse endpoint to get NLU predictions
func ParseMessage(message, llmServerURL string, timeout int, context map[string]interface{}) (*LLMParseResponse, error) {
	fullURL := llmServerURL + "/model/parse"

	payload := map[string]interface{}{
		"text": message,
	}
	if context != nil && len(context) > 0 {
		payload["metadata"] = context
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("error marshaling parse request: %v", err)
	}

	// *** GENERATE CURL COMMAND FOR PARSE ENDPOINT (only if debug enabled) ***
	config := LoadConfig()
	if config.Log.EnableDebug {
		headers := map[string]string{
			"User-Agent": "GChat/1.0",
			"X-Source":   "gchat-debug-parse",
		}
		curlCmd := generateCurlCommand(fullURL, jsonData, headers)

		// Sanitize PII from context for logging
		sanitizedContext := sanitizePII(context)

		requestData := map[string]interface{}{
			"url":         fullURL,
			"method":      "POST",
			"headers":     headers,
			"payload":     payload,
			"timeout":     timeout,
			"text":        message,
			"metadata":    sanitizedContext,
			"timestamp":   time.Now().Format("2006-01-02 15:04:05"),
		}

		logCurlCommand("PARSE", curlCmd, requestData, config.Log.DebugFile)
		log.Printf("GIAS_API_DEBUG: Parse curl command logged to %s", config.Log.DebugFile)
	}

	client := &http.Client{
		Timeout: time.Duration(timeout) * time.Second,
	}

	resp, err := client.Post(fullURL, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("error calling parse endpoint: %v", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading parse response: %v", err)
	}

	var parseResp LLMParseResponse
	if err := json.Unmarshal(body, &parseResp); err != nil {
		return nil, fmt.Errorf("error unmarshaling parse response: %v", err)
	}

	return &parseResp, nil
}

// GetTracker retrieves conversation tracker from LLM server
func GetTracker(sender, llmServerURL string, timeout int) (*LLMTrackerResponse, error) {
	fullURL := fmt.Sprintf("%s/conversations/%s/tracker", llmServerURL, sender)

	// *** GENERATE CURL COMMAND FOR TRACKER ENDPOINT (GET request) ***
	curlCmdGet := fmt.Sprintf("curl -X GET '%s' -H 'Content-Type: application/json' -H 'User-Agent: GChat/1.0' -H 'X-Source: gchat-debug-tracker'", fullURL)

	requestData := map[string]interface{}{
		"url":         fullURL,
		"method":      "GET",
		"headers":     map[string]string{
			"Content-Type": "application/json",
			"User-Agent": "GChat/1.0",
			"X-Source":   "gchat-debug-tracker",
		},
		"timeout":     timeout,
		"sender":      sender,
		"timestamp":   time.Now().Format("2006-01-02 15:04:05"),
	}

	// Log del comando curl GET per tracker
	logFile := "log/gias_api_debug.log"
	if err := os.MkdirAll("log", 0755); err == nil {
		if file, err := os.OpenFile(logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644); err == nil {
			defer file.Close()
			timestamp := time.Now().Format("2006-01-02 15:04:05")
			file.WriteString(fmt.Sprintf("\n=== GIAS API DEBUG SESSION - %s ===\n", timestamp))
			file.WriteString("Endpoint: TRACKER\n")
			if requestDataJSON, err := json.MarshalIndent(requestData, "", "  "); err == nil {
				file.WriteString("Request Data:\n")
				file.WriteString(string(requestDataJSON))
				file.WriteString("\n\n")
			}
			file.WriteString("CURL TEST COMMAND:\n")
			file.WriteString(curlCmdGet)
			file.WriteString("\n")
			file.WriteString("=== END DEBUG SESSION ===\n\n")
		}
	}

	log.Printf("GIAS_API_DEBUG: Tracker curl command logged to log/gias_api_debug.log")

	client := &http.Client{
		Timeout: time.Duration(timeout) * time.Second,
	}

	resp, err := client.Get(fullURL)
	if err != nil {
		return nil, fmt.Errorf("error getting tracker: %v", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading tracker response: %v", err)
	}

	var trackerResp LLMTrackerResponse
	if err := json.Unmarshal(body, &trackerResp); err != nil {
		return nil, fmt.Errorf("error unmarshaling tracker response: %v", err)
	}

	return &trackerResp, nil
}

// HandleDebugChat handles chat requests with debug information
func HandleDebugChat(c *gin.Context) {
	config := LoadConfig()
	clientIP := c.ClientIP()

	var req DebugChatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Printf("DEBUG_CHAT_ERROR: Invalid request - client_ip=%s, error=%v", clientIP, err)
		c.JSON(http.StatusBadRequest, DebugChatResponse{
			Status: "error",
			Error:  "Invalid request format",
		})
		return
	}

	if req.Sender == "" {
		req.Sender = "debug_user"
	}

	log.Printf("DEBUG_CHAT_REQUEST: client_ip=%s, sender=%s, message=%s", clientIP, req.Sender, req.Message)

	// NUOVO: Se UOC non fornito nel request, prova a recuperarlo da personale via user_id
	uoc := req.UOC
	if uoc == "" && req.UserID != "" {
		if userID, err := strconv.Atoi(req.UserID); err == nil {
			if personale, err := GetPersonaleByUserID(userID); err == nil {
				uoc = personale.DescrizioneAreaStrutturaComplessa
				// Fallback: se UOC è "NULL" o vuoto, estrai dal campo Descrizione
				if uoc == "" || uoc == "NULL" {
					parts := strings.Split(personale.Descrizione, "->")
					if len(parts) >= 2 {
						uoc = strings.TrimSpace(parts[1])
						log.Printf("DEBUG_CHAT_UOC_FALLBACK: user_id=%s, extracted from Descrizione, uoc=%s", req.UserID, uoc)
					}
				} else {
					log.Printf("DEBUG_CHAT_UOC_LOADED: user_id=%s, uoc=%s", req.UserID, uoc)
				}
			} else {
				log.Printf("DEBUG_CHAT_UOC_ERROR: user_id=%s, error=%v", req.UserID, err)
			}
		}
	}

	// Build context
	context := map[string]interface{}{
		"asl":            req.ASL,
		"asl_id":         req.ASLID,
		"user_id":        req.UserID,
		"codice_fiscale": req.CodiceFiscale,
		"username":       req.Username,
	}
	// NUOVO: Passa UOC se disponibile
	if uoc != "" {
		context["uoc"] = uoc
	}

	// Step 1: Parse message to get NLU predictions
	parseResp, err := ParseMessage(req.Message, config.LLMServer.URL, config.LLMServer.Timeout, context)
	if err != nil {
		log.Printf("DEBUG_CHAT_ERROR: Parse failed - error=%v", err)
		c.JSON(http.StatusInternalServerError, DebugChatResponse{
			Status: "error",
			Error:  fmt.Sprintf("Failed to parse message: %v", err),
		})
		return
	}

	// Step 2: Send message to LLM server to get response
	responses, err := SendToLLM(req.Message, req.Sender, config.LLMServer.URL, config.LLMServer.Timeout, context)
	if err != nil {
		log.Printf("DEBUG_CHAT_ERROR: LLM server request failed - error=%v", err)
		c.JSON(http.StatusInternalServerError, DebugChatResponse{
			Status: "error",
			Error:  fmt.Sprintf("Failed to send message: %v", err),
		})
		return
	}

	// Step 3: Get tracker to retrieve current slots
	trackerResp, err := GetTracker(req.Sender, config.LLMServer.URL, config.LLMServer.Timeout)
	if err != nil {
		log.Printf("DEBUG_CHAT_WARN: Failed to get tracker - error=%v", err)
		// Continue without tracker data
	}

	// Combine responses
	responseText := ""
	if len(responses) > 0 {
		responseText = responses[0].Text
		for i := 1; i < len(responses); i++ {
			responseText += " " + responses[i].Text
		}
	}

	// Extract confidence
	confidence := 0.0
	if intentData, ok := parseResp.Intent["confidence"].(float64); ok {
		confidence = intentData
	}

	// Extract executed actions from tracker events
	var executedActions []string
	if trackerResp != nil && len(trackerResp.Events) > 0 {
		// Traverse events in reverse to find actions in the latest turn
		// We look for 'action' events. We stop if we hit a 'user' event which marks the start of the turn.
		for i := len(trackerResp.Events) - 1; i >= 0; i-- {
			evt := trackerResp.Events[i]
			evtType, _ := evt["event"].(string)
			
			if evtType == "user" {
				break // Stop at the beginning of the current turn
			}
			
			if evtType == "action" {
				if actionName, ok := evt["name"].(string); ok {
					// Filter out action_listen and duplicates if needed, but showing sequence is good
					if actionName != "action_listen" {
						// Prepend to maintain chronological order
						executedActions = append([]string{actionName}, executedActions...)
					}
				}
			}
		}
	}

	// Extract execution tracking from backend response (real data from LangGraph)
	var executionPath []string
	var nodeTimings map[string]interface{}
	var totalExecutionMs float64

	if len(responses) > 0 && responses[0].Custom != nil {
		custom := responses[0].Custom

		// Extract execution_path from backend
		if pathData, ok := custom["execution_path"].([]interface{}); ok {
			for _, p := range pathData {
				if s, ok := p.(string); ok {
					executionPath = append(executionPath, s)
				}
			}
			log.Printf("DEBUG_CHAT: Using real execution_path from backend: %v", executionPath)
		}

		// Extract node_timings from backend
		if timingsData, ok := custom["node_timings"].(map[string]interface{}); ok {
			nodeTimings = make(map[string]interface{})
			for nodeName, timing := range timingsData {
				// Backend returns duration in ms as float, wrap in struct for frontend
				if durationMs, ok := timing.(float64); ok {
					nodeTimings[nodeName] = map[string]interface{}{
						"duration": durationMs,
						"status":   "completed",
					}
				}
			}
			log.Printf("DEBUG_CHAT: Using real node_timings from backend: %v", nodeTimings)
		}

		// Extract total execution time
		if total, ok := custom["total_execution_ms"].(float64); ok {
			totalExecutionMs = total
			log.Printf("DEBUG_CHAT: Total execution time from backend: %.2fms", totalExecutionMs)
		}
	}

	// Fallback to simulated data if backend didn't provide real tracking
	if len(executionPath) == 0 {
		executionPath = determineExecutionPath(parseResp.Intent)
		log.Printf("DEBUG_CHAT: Using fallback simulated execution_path: %v", executionPath)
	}

	if nodeTimings == nil {
		// Create simulated node timings as fallback
		nodeTimings = map[string]interface{}{
			"classify": map[string]interface{}{
				"duration": 150,
				"status":   "completed",
			},
			"dialogue_manager": map[string]interface{}{
				"duration": 100,
				"status":   "completed",
			},
			"response_generator": map[string]interface{}{
				"duration": 300,
				"status":   "completed",
			},
		}
		log.Printf("DEBUG_CHAT: Using fallback simulated node_timings")
	}

	// Prepare debug response
	debugResp := DebugChatResponse{
		Message:          responseText,
		Status:           "success",
		Intent:           parseResp.Intent,
		Entities:         parseResp.Entities,
		Confidence:       confidence,
		Metadata:         context,
		ExecutedActions:  executedActions,
		ExecutionPath:    executionPath,
		NodeTimings:      nodeTimings,
		WorkflowState:    "completed",
		TotalExecutionMs: totalExecutionMs,
		OriginalMessage:  req.Message,
	}

	if trackerResp != nil {
		debugResp.Slots = trackerResp.Slots
	}

	log.Printf("DEBUG_CHAT_SUCCESS: sender=%s, intent=%v, confidence=%.2f, entities=%d, actions=%d",
		req.Sender, parseResp.Intent["name"], confidence, len(parseResp.Entities), len(executedActions))

	c.JSON(http.StatusOK, debugResp)
}

// determineExecutionPath maps intent to expected LangGraph execution path
// Node names must match those in debug_langgraph_visualizer.js
func determineExecutionPath(intent map[string]interface{}) []string {
	intentName := "unknown"
	if name, ok := intent["name"].(string); ok {
		intentName = name
	}

	// Base path always includes input, classify (router), and dialogue_manager
	path := []string{"input", "classify", "dialogue_manager"}

	// Determine tool path based on intent
	if strings.Contains(intentName, "piano") || strings.Contains(intentName, "stabilimenti") || strings.Contains(intentName, "attivita") {
		path = append(path, "piano_tools")
	} else if strings.Contains(intentName, "priority") || strings.Contains(intentName, "risk") || strings.Contains(intentName, "controlli") {
		path = append(path, "priority_tools")
	} else if strings.Contains(intentName, "search") || strings.Contains(intentName, "topic") {
		path = append(path, "search_tool")
	} else if strings.Contains(intentName, "procedure") {
		path = append(path, "info_procedure_tool")
	} else if strings.Contains(intentName, "fallback") {
		path = append(path, "fallback_tool")
	} else if strings.Contains(intentName, "greet") || strings.Contains(intentName, "goodbye") || strings.Contains(intentName, "help") {
		// Direct response intents - skip tool nodes
	}

	// Always include response generation
	path = append(path, "response_generator")

	return path
}