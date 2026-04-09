package main

import (
	"net"
	"net/http"
	"time"
)

// Singleton http.Client riutilizzato per tutte le chiamate al backend.
// Evita di creare un nuovo pool TCP per ogni richiesta.
var backendHTTPClient = &http.Client{
	Timeout: 120 * time.Second, // timeout massimo (override per-request via context)
	Transport: &http.Transport{
		MaxIdleConns:        20,
		MaxIdleConnsPerHost: 10,
		IdleConnTimeout:     90 * time.Second,
		DialContext: (&net.Dialer{
			Timeout:   5 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,
	},
}

// Client con timeout breve per health check e metadata
var shortHTTPClient = &http.Client{
	Timeout: 10 * time.Second,
	Transport: &http.Transport{
		MaxIdleConns:        5,
		MaxIdleConnsPerHost: 5,
		IdleConnTimeout:     60 * time.Second,
		DialContext: (&net.Dialer{
			Timeout:   3 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,
	},
}
