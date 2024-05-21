package com.example.labelMark.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.HashMap;
import java.util.Map;


@Service
public class GeoServerService {

    @Value("${geoserver.url}")
    private String geoserverUrl;

    @Value("${geoserver.username}")
    private String username;

    @Value("${geoserver.password}")
    private String password;

    private final RestTemplate restTemplate;

    public GeoServerService(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    public String getGeoserverInfo(String mapServer) {
        String url = UriComponentsBuilder.fromHttpUrl(geoserverUrl)
                .pathSegment("rest", "workspaces", "LUU", "coveragestores", mapServer, "coverages", mapServer + ".json")
                .toUriString();

        HttpHeaders headers = new HttpHeaders();
        headers.setBasicAuth(username, password);

        ResponseEntity<String> response = restTemplate.getForEntity(url, String.class, headers);

        return response.getBody();
    }

    public ResponseEntity<byte[]> getGeoserverImg(String layerName, double width, double height, String bbox, String srs) {
        String url = UriComponentsBuilder.fromHttpUrl(geoserverUrl)
                .pathSegment("LUU", "wms")
                .toUriString();

        Map<String, String> params = new HashMap<>();
        params.put("service", "WMS");
        params.put("version", "1.1.0");
        params.put("request", "GetMap");
        params.put("layers", "LUU:" + layerName);
        params.put("styles", "");
        params.put("bbox", bbox);
        params.put("width", String.valueOf(width));
        params.put("height", String.valueOf(height));
        params.put("srs", srs);
        params.put("format", "image/jpeg");
        params.put("exceptions", "application/vnd.ogc.se_inimage");

        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(url);
        params.forEach(builder::queryParam);

        return restTemplate.getForEntity(builder.toUriString(), byte[].class);
    }
}