package com.example.labelMark.service;

import com.example.labelMark.domain.Server;
import com.baomidou.mybatisplus.extension.service.IService;

import java.util.List;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author hjw
 * @since 2024-05-16
 */
public interface ServerService extends IService<Server> {

    List<Server> getServers(Integer userId);

    int deleteServerByName(String serName);

    boolean createServer(Server server);
}
