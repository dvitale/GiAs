package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"mime/multipart"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

type TranscriptionResponse struct {
	Text     string `json:"text"`
	Language string `json:"language,omitempty"`
}

type WhisperResponse struct {
	Text string `json:"text"`
}

func TranscribeHandler(c *gin.Context) {
	startHandler := time.Now()

	file, err := c.FormFile("audio")
	if err != nil {
		log.Printf("ERROR_TRANSCRIBE: failed to receive audio file: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "File audio mancante"})
		return
	}

	language := c.PostForm("language")
	if language == "" {
		language = "it"
	}

	log.Printf("TRANSCRIBE_REQUEST: filename=%s, size=%d bytes, language=%s", file.Filename, file.Size, language)
	log.Printf("PROFILE_HANDLER_RECEIVE: %.2fms", time.Since(startHandler).Seconds()*1000)

	startTempFile := time.Now()
	tmpFile, err := os.CreateTemp("", "whisper-*.webm")
	if err != nil {
		log.Printf("ERROR_TRANSCRIBE: failed to create temp file: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Errore creazione file temporaneo"})
		return
	}
	defer os.Remove(tmpFile.Name())
	defer tmpFile.Close()

	src, err := file.Open()
	if err != nil {
		log.Printf("ERROR_TRANSCRIBE: failed to open uploaded file: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Errore apertura file"})
		return
	}
	defer src.Close()

	if _, err := io.Copy(tmpFile, src); err != nil {
		log.Printf("ERROR_TRANSCRIBE: failed to save uploaded file: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Errore salvataggio file"})
		return
	}

	tmpFile.Close()
	log.Printf("PROFILE_HANDLER_FILE_SAVE: %.2fms", time.Since(startTempFile).Seconds()*1000)

	whisperURL := os.Getenv("WHISPER_URL")
	if whisperURL == "" {
		whisperURL = "http://localhost:8090/inference"
	}

	log.Printf("TRANSCRIBE_WHISPER: sending to %s", whisperURL)

	startWhisper := time.Now()
	transcription, err := callWhisper(tmpFile.Name(), whisperURL, language)
	log.Printf("PROFILE_HANDLER_WHISPER_CALL: %.2fms (%.2fs)", time.Since(startWhisper).Seconds()*1000, time.Since(startWhisper).Seconds())
	if err != nil {
		log.Printf("ERROR_TRANSCRIBE: whisper call failed: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Errore trascrizione audio"})
		return
	}

	log.Printf("TRANSCRIBE_SUCCESS: text_length=%d", len(transcription))

	totalDuration := time.Since(startHandler)
	log.Printf("PROFILE_HANDLER_TOTAL: %.2fms (%.2fs)", totalDuration.Seconds()*1000, totalDuration.Seconds())

	c.JSON(http.StatusOK, TranscriptionResponse{
		Text:     transcription,
		Language: language,
	})
}

func callWhisper(audioPath, whisperURL, language string) (string, error) {
	startTotal := time.Now()

	// Use the passed whisperURL parameter instead of reading env again
	serverURL := whisperURL
	if serverURL == "" {
		// Fallback to env var for backward compatibility
		serverURL = os.Getenv("WHISPER_SERVER_URL")
		if serverURL == "" {
			serverURL = "http://localhost:8090/inference"
		}
	}

	startInference := time.Now()
	audioFile, err := os.Open(audioPath)
	if err != nil {
		return "", fmt.Errorf("failed to open audio file: %w", err)
	}
	defer audioFile.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	part, err := writer.CreateFormFile("file", "audio.wav")
	if err != nil {
		return "", fmt.Errorf("failed to create form file: %w", err)
	}
	if _, err := io.Copy(part, audioFile); err != nil {
		return "", fmt.Errorf("failed to copy audio data: %w", err)
	}

	// Add language parameter if provided
	if language != "" {
		languageField, err := writer.CreateFormField("language")
		if err != nil {
			return "", fmt.Errorf("failed to create language field: %w", err)
		}
		if _, err := languageField.Write([]byte(language)); err != nil {
			return "", fmt.Errorf("failed to write language field: %w", err)
		}
		log.Printf("TRANSCRIBE_LANGUAGE: Sending language parameter: %s", language)
	}

	writer.Close()

	req, err := http.NewRequest("POST", serverURL, body)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	log.Printf("TRANSCRIBE_FASTER_WHISPER: POST %s", serverURL)

	client := &http.Client{Timeout: 20 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("faster-whisper server request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("faster-whisper server returned status %d: %s", resp.StatusCode, string(bodyBytes))
	}

	var result struct {
		Text     string  `json:"text"`
		Duration float64 `json:"duration"`
		Language string  `json:"language"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode response: %w", err)
	}

	inferDuration := time.Since(startInference)
	log.Printf("PROFILE_WHISPER_INFERENCE: %.2fms (%.2fs) [server reported: %.2fs]", inferDuration.Seconds()*1000, inferDuration.Seconds(), result.Duration)

	totalDuration := time.Since(startTotal)
	log.Printf("PROFILE_TOTAL: %.2fms (%.2fs)", totalDuration.Seconds()*1000, totalDuration.Seconds())

	return strings.TrimSpace(result.Text), nil
}
