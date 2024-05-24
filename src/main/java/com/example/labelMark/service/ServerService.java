package com.example.labelMark.service;

import com.example.labelMark.domain.Server;
import com.baomidou.mybatisplus.extension.service.IService;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author hjw
 * @since 2024-04-15
 */
@Service
public interface ServerService extends IService<Server> {

    List<Server> getServers();

    int deleteServerByName(String serName);

    boolean createServer(Server server);
}
