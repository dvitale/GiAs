package main

import (
	"crypto/rand"
	"encoding/hex"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gin-contrib/sessions"
	"github.com/gin-gonic/gin"
)

// ---------------------------------------------------------------------------
// Rate Limiting — token bucket per IP, applicato solo agli endpoint chat
// ---------------------------------------------------------------------------

type rateBucket struct {
	tokens    float64
	lastCheck time.Time
}

type rateLimiter struct {
	mu       sync.Mutex
	buckets  map[string]*rateBucket
	rate     float64 // token al secondo
	capacity float64 // burst massimo
}

func newRateLimiter(ratePerSecond, burst float64) *rateLimiter {
	rl := &rateLimiter{
		buckets:  make(map[string]*rateBucket),
		rate:     ratePerSecond,
		capacity: burst,
	}
	// Pulizia periodica dei bucket inattivi
	go func() {
		for {
			time.Sleep(5 * time.Minute)
			rl.mu.Lock()
			cutoff := time.Now().Add(-10 * time.Minute)
			for key, b := range rl.buckets {
				if b.lastCheck.Before(cutoff) {
					delete(rl.buckets, key)
				}
			}
			rl.mu.Unlock()
		}
	}()
	return rl
}

func (rl *rateLimiter) allow(key string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	b, exists := rl.buckets[key]
	if !exists {
		rl.buckets[key] = &rateBucket{tokens: rl.capacity - 1, lastCheck: now}
		return true
	}

	// Ricarica token in base al tempo trascorso
	elapsed := now.Sub(b.lastCheck).Seconds()
	b.tokens += elapsed * rl.rate
	if b.tokens > rl.capacity {
		b.tokens = rl.capacity
	}
	b.lastCheck = now

	if b.tokens < 1 {
		return false
	}
	b.tokens--
	return true
}

// chatRateLimiter: 2 richieste/secondo, burst di 5
var chatRateLimiter = newRateLimiter(2.0, 5.0)

// RateLimitMiddleware limita le richieste chat per IP
func RateLimitMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		key := c.ClientIP()
		if !chatRateLimiter.allow(key) {
			log.Printf("RATE_LIMIT: blocked request from ip=%s, path=%s", key, c.Request.URL.Path)
			c.JSON(http.StatusTooManyRequests, gin.H{
				"status": "error",
				"error":  "Troppe richieste, riprova tra qualche secondo",
			})
			c.Abort()
			return
		}
		c.Next()
	}
}

// ---------------------------------------------------------------------------
// CSRF Protection — token sincronizzato via sessione
// ---------------------------------------------------------------------------

const csrfTokenKey = "csrf_token"
const csrfHeaderName = "X-CSRF-Token"

// generateCSRFToken genera un token casuale di 32 byte (hex encoded)
func generateCSRFToken() string {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		// Fallback improbabile ma sicuro
		return hex.EncodeToString([]byte(time.Now().String()))
	}
	return hex.EncodeToString(b)
}

// EnsureCSRFToken garantisce che la sessione abbia un token CSRF e lo rende disponibile
// nel context Gin per l'injection nei template
func EnsureCSRFToken() gin.HandlerFunc {
	return func(c *gin.Context) {
		session := sessions.Default(c)
		token := session.Get(csrfTokenKey)
		if token == nil || token == "" {
			newToken := generateCSRFToken()
			session.Set(csrfTokenKey, newToken)
			if err := session.Save(); err != nil {
				log.Printf("CSRF_TOKEN_SAVE_ERROR: %v", err)
			}
			token = newToken
		}
		// Rendi disponibile ai template e al JS via header
		c.Set("csrf_token", token)
		c.Header("X-CSRF-Token", token.(string))
		c.Next()
	}
}

// ValidateCSRF verifica il token CSRF sulle richieste state-changing (POST/PUT/DELETE).
// Esenzioni: endpoint SSE/streaming, proxy admin (interni), e API JSON senza cookie session.
func ValidateCSRF() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Solo metodi state-changing
		if c.Request.Method == "GET" || c.Request.Method == "HEAD" || c.Request.Method == "OPTIONS" {
			c.Next()
			return
		}

		// Richieste JSON non sono vulnerabili a CSRF (browser non puo' inviare JSON cross-origin via form)
		if strings.Contains(c.GetHeader("Content-Type"), "application/json") {
			c.Next()
			return
		}

		session := sessions.Default(c)
		expectedToken, _ := session.Get(csrfTokenKey).(string)

		if expectedToken == "" {
			// Nessuna sessione attiva — skip (prima visita, API call diretta)
			c.Next()
			return
		}

		// Controlla header X-CSRF-Token
		providedToken := c.GetHeader(csrfHeaderName)
		if providedToken == "" {
			// Fallback: controlla form field
			providedToken = c.PostForm("_csrf_token")
		}

		if providedToken != expectedToken {
			log.Printf("CSRF_VALIDATION_FAILED: client_ip=%s, path=%s, method=%s",
				c.ClientIP(), c.Request.URL.Path, c.Request.Method)
			c.JSON(http.StatusForbidden, gin.H{
				"status": "error",
				"error":  "Token CSRF non valido",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}
