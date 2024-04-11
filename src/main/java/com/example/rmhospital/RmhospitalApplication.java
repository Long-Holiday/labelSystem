package com.example.rmhospital;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.web.servlet.ServletComponentScan;
import org.springframework.context.annotation.Bean;
import springfox.documentation.oas.annotations.EnableOpenApi;

@SpringBootApplication
@EnableOpenApi
@ServletComponentScan(basePackages = "com.example.rmhospital")
public class RmhospitalApplication {

    public static void main(String[] args) {
        SpringApplication.run(RmhospitalApplication.class, args);
    }
    @Bean
    public ApplicationRunner applicationRunner() {
        return args -> {
            System.out.println("------------------------------------------------------------------------");
            System.out.println("你可以在浏览器中访问 http://localhost:1290/swagger-ui/index.html 来查看你的API文档。");
            System.out.println("------------------------------------------------------------------------");

        };
    }
}
