package com.example.labelMark.utils;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.Base64;

@Service
public class GeoServerRESTClient {

    private static final String GEOSERVER_REST_URL = "http://localhost:8080/geoserver/rest";
    private static final String WORKSPACE = "LUU";
    private static final String DATASTORE = "country";
    private static final String LAYER = "country";
    private static final String USERNAME = "admin";
    private static final String PASSWORD = "geoserver";

    public String GeoServerString (String filename) {
        try {
            String layersEndpoint = GEOSERVER_REST_URL + "/workspaces/" + WORKSPACE + "/datastores/" + DATASTORE + "/featuretypes/"+filename+".json";
            String auth = USERNAME + ":" + PASSWORD;
            String encodedAuth = Base64.getEncoder().encodeToString(auth.getBytes());

            URL url = new URL(layersEndpoint);
            HttpURLConnection con = (HttpURLConnection) url.openConnection();
            con.setRequestMethod("GET");
            con.setRequestProperty("Authorization", "Basic " + encodedAuth);

            int responseCode = con.getResponseCode();
            if (responseCode == HttpURLConnection.HTTP_OK) {
                BufferedReader in = new BufferedReader(new InputStreamReader(con.getInputStream()));
                String inputLine;
                StringBuilder response = new StringBuilder();
                while ((inputLine = in.readLine()) != null) {
                    response.append(inputLine);
                }
                in.close();

                // 处理获取到的图层信息
                return response.toString();
            } else {
                return "GET request not worked. Response code: " + responseCode;

            }
        } catch (Exception e) {
            e.printStackTrace();
            return "ERROR";
        }

    }
}
