package com.example.labelMark;

import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration;
import org.springframework.boot.web.servlet.ServletComponentScan;
import org.springframework.context.annotation.Bean;
import org.springframework.web.client.RestTemplate;
import springfox.documentation.oas.annotations.EnableOpenApi;

/**
 * @Description
 * @Author wh
 * @Date 2024/4/15
 */

@SpringBootApplication
@EnableOpenApi
@ServletComponentScan(basePackages = "com.example.labelMark")
public class LabelMarkApplication {
    public static void main(String[] args) {
        SpringApplication.run(LabelMarkApplication.class, args);
    }

    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}
