package com.example.labelMark.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.example.labelMark.domain.sysFile;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author hjw
 * @since 2024-04-18
 */
@Service
public interface sysFileService extends IService<sysFile> {

    List<sysFile> getAllFiles(Integer current, Integer pageSize, Integer fileId);

    void updateFile(Integer fileId, String fileName);

    void deleteFile(String fileName);
}
