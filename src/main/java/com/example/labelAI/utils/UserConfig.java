package com.example.labelAI.utils;

import lombok.Data;

@Data
public class UserConfig {
    private String username;
    private String password;
    private String url;
    private String driverClassName;

    public UserConfig(String username, String password, String url, String driverClassName) {
        this.username = username;
        this.password = password;
        this.url = url;
        this.driverClassName = driverClassName;
    }
}
